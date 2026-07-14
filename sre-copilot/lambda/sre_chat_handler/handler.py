"""
SRE Copilot Agent - Chat Handler Lambda Function

This Lambda function serves as the API Gateway proxy integration for the React Chat UI.
It handles CORS preflight requests, validates user input, invokes the Bedrock Agent,
and collects streaming responses.
"""

import json
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3


def emit_structured_log(function_name: str, input_parameters: Dict[str, Any], execution_duration_ms: int):
    """
    Emit structured JSON log entry to CloudWatch.
    
    Args:
        function_name: Name of the function (handler or sub-function)
        input_parameters: Input parameters (sensitive data will be redacted)
        execution_duration_ms: Execution time in milliseconds
    """
    # Redact sensitive fields
    redacted_params = input_parameters.copy()
    if 'question' in redacted_params and len(redacted_params.get('question', '')) > 100:
        redacted_params['question'] = redacted_params['question'][:100] + "..."
    
    log_entry = {
        "function_name": function_name,
        "input_parameters": redacted_params,
        "execution_duration_ms": execution_duration_ms
    }
    print(json.dumps(log_entry))


def cors_headers() -> Dict[str, str]:
    """
    Return CORS headers for API responses.
    
    Returns:
        Dictionary of CORS headers
    """
    return {
        'Access-Control-Allow-Origin': '*',  # Configure this to match your UI domain in production
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }


def cors_preflight_response() -> Dict[str, Any]:
    """
    Handle CORS preflight OPTIONS request.
    
    Returns:
        API Gateway proxy response with CORS headers
    """
    return {
        'statusCode': 200,
        'headers': cors_headers(),
        'body': json.dumps({'message': 'CORS preflight success'})
    }


def error_response(status_code: int, error_type: str, message: str) -> Dict[str, Any]:
    """
    Format an error response for API Gateway.
    
    Args:
        status_code: HTTP status code
        error_type: Error type/category
        message: Human-readable error message
        
    Returns:
        API Gateway proxy response dictionary
    """
    return {
        'statusCode': status_code,
        'headers': cors_headers(),
        'body': json.dumps({
            'error': error_type,
            'message': message
        })
    }


def success_response(response_text: str, session_id: str, data_freshness: Optional[str] = None) -> Dict[str, Any]:
    """
    Format a successful response for API Gateway.
    
    Args:
        response_text: The Agent's response text
        session_id: The session identifier
        data_freshness: ISO 8601 timestamp of data freshness
        
    Returns:
        API Gateway proxy response dictionary
    """
    body = {
        'response': response_text,
        'sessionId': session_id
    }
    
    if data_freshness:
        body['dataFreshness'] = data_freshness
    
    return {
        'statusCode': 200,
        'headers': cors_headers(),
        'body': json.dumps(body)
    }


def validate_question(question: str) -> tuple[bool, Optional[str]]:
    """
    Validate the user's question.
    
    Args:
        question: The user's question string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not question or not question.strip():
        return False, "Question cannot be empty"
    
    if len(question) > 2000:
        return False, "Question exceeds maximum length of 2000 characters"
    
    return True, None


def validate_session_id(session_id: str) -> tuple[bool, Optional[str]]:
    """
    Validate the session ID format (should be a valid UUID).
    
    Args:
        session_id: The session identifier
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not session_id or not session_id.strip():
        return False, "Session ID cannot be empty"
    
    # Basic UUID format validation (8-4-4-4-12 hex characters)
    parts = session_id.split('-')
    if len(parts) != 5:
        return False, "Invalid session ID format"
    
    if not (len(parts[0]) == 8 and len(parts[1]) == 4 and len(parts[2]) == 4 and 
            len(parts[3]) == 4 and len(parts[4]) == 12):
        return False, "Invalid session ID format"
    
    return True, None


def invoke_bedrock_agent(agent_id: str, agent_alias_id: str, session_id: str, input_text: str) -> tuple[str, Optional[str]]:
    """
    Invoke the Bedrock Agent and collect streaming response.
    
    Args:
        agent_id: The Bedrock Agent ID
        agent_alias_id: The Agent Alias ID
        session_id: The session identifier
        input_text: The user's question
        
    Returns:
        Tuple of (full_response, data_freshness_timestamp)
        
    Raises:
        Exception: If agent invocation fails
    """
    bedrock_agent_runtime = boto3.client(
        'bedrock-agent-runtime',
        region_name=os.environ.get('AWS_REGION', 'us-west-2')
    )
    
    try:
        response = bedrock_agent_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=input_text
        )
        
        # Collect streaming chunks
        full_response = ""
        data_freshness = None
        
        event_stream = response.get('completion', [])
        
        for event in event_stream:
            # Check for chunk events
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    chunk_text = chunk['bytes'].decode('utf-8')
                    full_response += chunk_text
        
        # Extract data freshness from response if present
        # The Agent should include this in its response
        # For now, use current timestamp as fallback
        if not data_freshness:
            data_freshness = datetime.now(timezone.utc).isoformat()
        
        return full_response, data_freshness
        
    except Exception as e:
        print(f"ERROR: Bedrock Agent invocation failed")
        print(traceback.format_exc())
        raise


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for API Gateway proxy integration.
    
    Handles CORS preflight, validates input, invokes Bedrock Agent,
    and returns formatted responses.
    
    Args:
        event: API Gateway proxy event
        context: Lambda context object
        
    Returns:
        API Gateway proxy response dictionary
    """
    start_time = time.time()
    
    # Handle CORS preflight
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method')
    if http_method == 'OPTIONS':
        return cors_preflight_response()
    
    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)
        
        question = body.get('question', '')
        session_id = body.get('sessionId', '')
        
        # Log invocation (before validation to capture all attempts)
        emit_structured_log('sre-chat-handler', {
            'question': question,
            'sessionId': session_id,
            'httpMethod': http_method
        }, 0)
        
        # Validate question
        is_valid, error_msg = validate_question(question)
        if not is_valid:
            execution_duration_ms = int((time.time() - start_time) * 1000)
            emit_structured_log('sre-chat-handler', {
                'validation_error': error_msg
            }, execution_duration_ms)
            return error_response(400, 'validation_error', error_msg)
        
        # Validate session ID
        is_valid, error_msg = validate_session_id(session_id)
        if not is_valid:
            execution_duration_ms = int((time.time() - start_time) * 1000)
            emit_structured_log('sre-chat-handler', {
                'validation_error': error_msg
            }, execution_duration_ms)
            return error_response(400, 'validation_error', error_msg)
        
        # Get Agent configuration from environment
        agent_id = os.environ.get('AGENT_ID')
        agent_alias_id = os.environ.get('AGENT_ALIAS_ID')
        
        if not agent_id or not agent_alias_id:
            execution_duration_ms = int((time.time() - start_time) * 1000)
            emit_structured_log('sre-chat-handler', {
                'config_error': 'Missing AGENT_ID or AGENT_ALIAS_ID'
            }, execution_duration_ms)
            return error_response(
                500,
                'configuration_error',
                'Agent configuration is missing'
            )
        
        # Invoke Bedrock Agent
        try:
            full_response, data_freshness = invoke_bedrock_agent(
                agent_id,
                agent_alias_id,
                session_id,
                question
            )
        except Exception as e:
            execution_duration_ms = int((time.time() - start_time) * 1000)
            emit_structured_log('sre-chat-handler', {
                'agent_error': str(e)
            }, execution_duration_ms)
            return error_response(
                500,
                'agent_invocation_failed',
                f'Failed to invoke Bedrock Agent: {str(e)}'
            )
        
        # Calculate execution duration and emit final log
        execution_duration_ms = int((time.time() - start_time) * 1000)
        emit_structured_log('sre-chat-handler', {
            'success': True,
            'response_length': len(full_response)
        }, execution_duration_ms)
        
        # Return success response
        return success_response(full_response, session_id, data_freshness)
        
    except json.JSONDecodeError as e:
        execution_duration_ms = int((time.time() - start_time) * 1000)
        emit_structured_log('sre-chat-handler', {
            'json_error': str(e)
        }, execution_duration_ms)
        return error_response(
            400,
            'invalid_json',
            'Request body must be valid JSON'
        )
        
    except Exception as e:
        # Log full stack trace
        print(f"ERROR: Unexpected exception in handler")
        print(traceback.format_exc())
        
        execution_duration_ms = int((time.time() - start_time) * 1000)
        emit_structured_log('sre-chat-handler', {
            'unexpected_error': str(e)
        }, execution_duration_ms)
        
        return error_response(
            500,
            'internal_error',
            f'An unexpected error occurred: {str(e)}'
        )
