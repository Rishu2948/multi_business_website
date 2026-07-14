"""
SRE Copilot Agent - Gold Query Tools Lambda Handler

This Lambda function serves as the Action Group handler for the Bedrock Agent.
It routes incoming function calls to the appropriate Gold table query functions
and manages Databricks SQL connections with credential caching.
"""

import json
import os
import time
import traceback
from typing import Any, Dict, List, Optional

import boto3
from databricks import sql as dbsql


# Module-level credential cache for warm invocations
_DATABRICKS_TOKEN: Optional[str] = None


class SecretsManagerUnavailableError(Exception):
    """Raised when Secrets Manager is unreachable at cold start."""
    pass


def get_databricks_token() -> str:
    """
    Retrieve Databricks PAT from Secrets Manager.
    
    Caches the token at module level to reduce Secrets Manager API calls
    on warm Lambda invocations.
    
    Returns:
        str: The Databricks Personal Access Token
        
    Raises:
        SecretsManagerUnavailableError: If Secrets Manager is unreachable
    """
    global _DATABRICKS_TOKEN
    
    if _DATABRICKS_TOKEN is None:
        sm_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-west-2'))
        try:
            response = sm_client.get_secret_value(SecretId='sre/databricks-pat')
            _DATABRICKS_TOKEN = response['SecretString']
        except Exception as e:
            raise SecretsManagerUnavailableError(f"Failed to retrieve Databricks PAT: {str(e)}")
    
    return _DATABRICKS_TOKEN


def get_databricks_connection():
    """
    Establish a connection to Databricks SQL warehouse.
    
    Uses environment variables for host and http_path configuration,
    and retrieves the access token from Secrets Manager.
    
    Returns:
        databricks.sql.Connection: Active Databricks SQL connection
        
    Raises:
        SecretsManagerUnavailableError: If token retrieval fails
        Exception: If connection to Databricks fails
    """
    token = get_databricks_token()
    
    host = os.environ.get('DATABRICKS_HOST')
    http_path = os.environ.get('DATABRICKS_HTTP_PATH')
    
    if not host or not http_path:
        raise ValueError("DATABRICKS_HOST and DATABRICKS_HTTP_PATH environment variables must be set")
    
    connection = dbsql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token
    )
    
    return connection


def redact_credentials(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive credential fields from parameters for logging.
    
    Args:
        params: Dictionary of parameters to redact
        
    Returns:
        Dictionary with credentials replaced with "[REDACTED]"
    """
    redacted = params.copy()
    sensitive_keys = ['token', 'password', 'secret', 'api_key', 'access_token', 'pat']
    
    for key in redacted:
        if any(sensitive in key.lower() for sensitive in sensitive_keys):
            redacted[key] = "[REDACTED]"
    
    return redacted


def emit_structured_log(function_name: str, input_parameters: Dict[str, Any], execution_duration_ms: int):
    """
    Emit structured JSON log entry to CloudWatch.
    
    Args:
        function_name: Name of the invoked function
        input_parameters: Input parameters (will be redacted)
        execution_duration_ms: Execution time in milliseconds
    """
    log_entry = {
        "function_name": function_name,
        "input_parameters": redact_credentials(input_parameters),
        "execution_duration_ms": execution_duration_ms
    }
    print(json.dumps(log_entry))


def success_response(action_group: str, function: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a successful response for Bedrock Action Group v1.0 schema.
    
    Args:
        action_group: The action group name
        function: The function name
        result: The query result dictionary
        
    Returns:
        Formatted response dictionary
    """
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "function": function,
            "functionResponse": {
                "responseBody": {
                    "TEXT": {
                        "body": json.dumps(result)
                    }
                }
            }
        }
    }


def error_response(action_group: str, function: str, error_type: str, message: str, service: Optional[str] = None) -> Dict[str, Any]:
    """
    Format an error response for Bedrock Action Group v1.0 schema.
    
    Args:
        action_group: The action group name
        function: The function name
        error_type: Type/category of the error
        message: Human-readable error message
        service: Optional service name related to the error
        
    Returns:
        Formatted error response dictionary
    """
    error_body = {
        "error": error_type,
        "message": message
    }
    
    if service:
        error_body["service"] = service
    
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "function": function,
            "functionResponse": {
                "responseBody": {
                    "TEXT": {
                        "body": json.dumps(error_body)
                    }
                }
            }
        }
    }


def extract_parameters(parameters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract parameters from Bedrock Action Group parameter format.
    
    Args:
        parameters: List of parameter dictionaries with 'name', 'type', 'value' keys
        
    Returns:
        Dictionary mapping parameter names to values
    """
    return {param['name']: param['value'] for param in parameters}


def query_service_health(conn, service: str, region: Optional[str] = None) -> Dict[str, Any]:
    """
    Query the gold.service_health table for a specific service.
    
    Args:
        conn: Databricks SQL connection
        service: Service name to query
        region: Optional region filter (defaults to all regions)
        
    Returns:
        Dictionary containing service health data
    """
    cursor = conn.cursor()
    
    if region:
        query = """
            SELECT service, region, overall_health, status, timestamp_hour
            FROM gold.service_health
            WHERE service = ? AND region = ?
            ORDER BY timestamp_hour DESC
            LIMIT 1
        """
        cursor.execute(query, (service, region))
    else:
        query = """
            SELECT service, region, overall_health, status, timestamp_hour
            FROM gold.service_health
            WHERE service = ?
            ORDER BY timestamp_hour DESC
            LIMIT 1
        """
        cursor.execute(query, (service,))
    
    row = cursor.fetchone()
    cursor.close()
    
    if row:
        return {
            "service": row[0],
            "region": row[1],
            "overall_health": row[2],
            "status": row[3],
            "timestamp_hour": str(row[4])
        }
    else:
        return {
            "service": service,
            "message": "No health data available for this service"
        }


def query_error_summary(conn, service: str, hours_back: Optional[int] = 6, region: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Query the gold.error_summaries table for recent error summaries.
    
    Args:
        conn: Databricks SQL connection
        service: Service name to query
        hours_back: Number of hours to look back (default: 6)
        region: Optional region filter
        
    Returns:
        List of error summary dictionaries
    """
    cursor = conn.cursor()
    
    hours_back = hours_back or 6
    
    if region:
        query = """
            SELECT hour, service, region, total_errors, total_warnings, 
                   error_rate_vs_normal, is_anomalous, trend_direction, nl_summary
            FROM gold.error_summaries
            WHERE service = ? 
              AND region = ?
              AND hour >= current_timestamp() - INTERVAL ? HOURS
            ORDER BY hour DESC
            LIMIT 12
        """
        cursor.execute(query, (service, region, hours_back))
    else:
        query = """
            SELECT hour, service, region, total_errors, total_warnings, 
                   error_rate_vs_normal, is_anomalous, trend_direction, nl_summary
            FROM gold.error_summaries
            WHERE service = ?
              AND hour >= current_timestamp() - INTERVAL ? HOURS
            ORDER BY hour DESC
            LIMIT 12
        """
        cursor.execute(query, (service, hours_back))
    
    rows = cursor.fetchall()
    cursor.close()
    
    results = []
    for row in rows:
        results.append({
            "hour": str(row[0]),
            "service": row[1],
            "region": row[2],
            "total_errors": row[3],
            "total_warnings": row[4],
            "error_rate_vs_normal": row[5],
            "is_anomalous": row[6],
            "trend_direction": row[7],
            "nl_summary": row[8]
        })
    
    return results


def query_error_patterns(conn, service: str) -> List[Dict[str, Any]]:
    """
    Query the gold.error_patterns table for known error patterns.
    
    Args:
        conn: Databricks SQL connection
        service: Service name to query
        
    Returns:
        List of error pattern dictionaries
    """
    cursor = conn.cursor()
    
    query = """
        SELECT pattern_id, service, error_type, error_category, canonical_message,
               occurrences_24h, trend_7d, is_new_pattern, known_resolution, last_seen
        FROM gold.error_patterns
        WHERE service = ?
        ORDER BY occurrences_24h DESC
        LIMIT 10
    """
    cursor.execute(query, (service,))
    
    rows = cursor.fetchall()
    cursor.close()
    
    results = []
    for row in rows:
        results.append({
            "pattern_id": row[0],
            "service": row[1],
            "error_type": row[2],
            "error_category": row[3],
            "canonical_message": row[4],
            "occurrences_24h": row[5],
            "trend_7d": row[6],
            "is_new_pattern": row[7],
            "known_resolution": row[8],
            "last_seen": str(row[9])
        })
    
    return results


def query_historical_trend(conn, service: str, days_back: Optional[int] = 7) -> List[Dict[str, Any]]:
    """
    Query historical error trends from gold.error_summaries.
    
    Args:
        conn: Databricks SQL connection
        service: Service name to query
        days_back: Number of days to look back (default: 7)
        
    Returns:
        List of historical trend data dictionaries
    """
    cursor = conn.cursor()
    
    days_back = days_back or 7
    
    query = """
        SELECT DATE(hour) as date, service, 
               SUM(total_errors) as daily_errors,
               AVG(error_rate_vs_normal) as avg_error_rate,
               MAX(is_anomalous) as had_anomaly
        FROM gold.error_summaries
        WHERE service = ?
          AND hour >= current_timestamp() - INTERVAL ? DAYS
        GROUP BY DATE(hour), service
        ORDER BY date DESC
        LIMIT 12
    """
    cursor.execute(query, (service, days_back))
    
    rows = cursor.fetchall()
    cursor.close()
    
    results = []
    for row in rows:
        results.append({
            "date": str(row[0]),
            "service": row[1],
            "daily_errors": row[2],
            "avg_error_rate": row[3],
            "had_anomaly": row[4]
        })
    
    return results


def get_service_dependencies(conn, service: str) -> List[Dict[str, Any]]:
    """
    Query service dependencies from config.dependencies table.
    
    Args:
        conn: Databricks SQL connection
        service: Service name to query
        
    Returns:
        List of service dependency dictionaries
    """
    cursor = conn.cursor()
    
    query = """
        SELECT source_service, target_service, dependency_type, protocol
        FROM config.dependencies
        WHERE source_service = ? OR target_service = ?
        LIMIT 12
    """
    cursor.execute(query, (service, service))
    
    rows = cursor.fetchall()
    cursor.close()
    
    results = []
    for row in rows:
        results.append({
            "source_service": row[0],
            "target_service": row[1],
            "dependency_type": row[2],
            "protocol": row[3]
        })
    
    return results


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for Bedrock Action Group.
    
    Routes function calls to appropriate query functions and handles errors.
    
    Args:
        event: Bedrock Action Group v1.0 event
        context: Lambda context object
        
    Returns:
        Formatted response dictionary
    """
    start_time = time.time()
    
    # Extract event details
    action_group = event.get('actionGroup', 'sre-gold-tools')
    function_name = event.get('function', 'unknown')
    parameters = event.get('parameters', [])
    
    # Convert parameters to dictionary
    params = extract_parameters(parameters)
    
    try:
        # Emit structured log at invocation start
        emit_structured_log(function_name, params, 0)
        
        # Check if Secrets Manager is available (cold start check)
        try:
            token = get_databricks_token()
        except SecretsManagerUnavailableError as e:
            # Return error and make NO downstream calls
            execution_duration_ms = int((time.time() - start_time) * 1000)
            emit_structured_log(function_name, params, execution_duration_ms)
            return error_response(
                action_group,
                function_name,
                "secrets_unavailable",
                "Unable to retrieve credentials from Secrets Manager",
                params.get('service')
            )
        
        # Establish Databricks connection
        conn = get_databricks_connection()
        
        # Route to appropriate function
        result = None
        service = params.get('service')
        
        if function_name == 'query_service_health':
            region = params.get('region')
            result = query_service_health(conn, service, region)
            
        elif function_name == 'query_error_summary':
            hours_back = int(params.get('hours_back', 6))
            region = params.get('region')
            result = query_error_summary(conn, service, hours_back, region)
            
        elif function_name == 'query_error_patterns':
            result = query_error_patterns(conn, service)
            
        elif function_name == 'query_historical_trend':
            days_back = int(params.get('days_back', 7))
            result = query_historical_trend(conn, service, days_back)
            
        elif function_name == 'get_service_dependencies':
            result = get_service_dependencies(conn, service)
            
        else:
            conn.close()
            execution_duration_ms = int((time.time() - start_time) * 1000)
            emit_structured_log(function_name, params, execution_duration_ms)
            return error_response(
                action_group,
                function_name,
                "unknown_function",
                f"Function '{function_name}' is not recognized",
                service
            )
        
        # Close connection
        conn.close()
        
        # Calculate execution duration and emit final log
        execution_duration_ms = int((time.time() - start_time) * 1000)
        emit_structured_log(function_name, params, execution_duration_ms)
        
        # Return success response
        return success_response(action_group, function_name, result)
        
    except Exception as e:
        # Log full stack trace
        print(f"ERROR: Exception in {function_name}")
        print(traceback.format_exc())
        
        # Calculate execution duration
        execution_duration_ms = int((time.time() - start_time) * 1000)
        emit_structured_log(function_name, params, execution_duration_ms)
        
        # Determine error type
        error_type = type(e).__name__
        
        # Return structured error response
        return error_response(
            action_group,
            function_name,
            error_type,
            str(e),
            params.get('service')
        )
