"""
Pytest configuration and shared fixtures for sre_gold_query_tools tests.
"""

import os
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    monkeypatch.setenv('DATABRICKS_HOST', 'community.cloud.databricks.com')
    monkeypatch.setenv('DATABRICKS_HTTP_PATH', '/sql/1.0/warehouses/test-warehouse-id')


@pytest.fixture
def mock_secrets_manager(monkeypatch):
    """Mock boto3 Secrets Manager client."""
    mock_sm_client = Mock()
    mock_sm_client.get_secret_value.return_value = {
        'SecretString': 'test-databricks-token-12345'
    }
    
    def mock_boto3_client(service_name, region_name=None):
        if service_name == 'secretsmanager':
            return mock_sm_client
        return Mock()
    
    import boto3
    monkeypatch.setattr(boto3, 'client', mock_boto3_client)
    
    return mock_sm_client


@pytest.fixture
def mock_secrets_manager_unavailable(monkeypatch):
    """Mock boto3 Secrets Manager client that raises an error."""
    mock_sm_client = Mock()
    mock_sm_client.get_secret_value.side_effect = Exception("Secrets Manager is unavailable")
    
    def mock_boto3_client(service_name, region_name=None):
        if service_name == 'secretsmanager':
            return mock_sm_client
        return Mock()
    
    import boto3
    monkeypatch.setattr(boto3, 'client', mock_boto3_client)
    
    return mock_sm_client


@pytest.fixture
def mock_databricks_connection():
    """Mock Databricks SQL connection and cursor."""
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.close.return_value = None
    
    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close.return_value = None
    
    return mock_conn, mock_cursor


@pytest.fixture
def mock_databricks_sql(monkeypatch, mock_databricks_connection):
    """Mock the databricks.sql module."""
    mock_conn, mock_cursor = mock_databricks_connection
    
    mock_dbsql = Mock()
    mock_dbsql.connect.return_value = mock_conn
    
    # Patch the databricks.sql import
    import sys
    from unittest.mock import MagicMock
    
    # Create a mock databricks module
    mock_databricks = MagicMock()
    mock_databricks.sql = mock_dbsql
    
    sys.modules['databricks'] = mock_databricks
    sys.modules['databricks.sql'] = mock_dbsql
    
    return mock_dbsql, mock_conn, mock_cursor


@pytest.fixture
def sample_bedrock_event() -> Dict[str, Any]:
    """Sample Bedrock Action Group v1.0 event."""
    return {
        "messageVersion": "1.0",
        "agent": {
            "name": "sre-copilot",
            "id": "test-agent-id",
            "alias": "live",
            "version": "1"
        },
        "actionGroup": "sre-gold-tools",
        "function": "query_service_health",
        "parameters": [
            {"name": "service", "type": "string", "value": "checkout-service"},
            {"name": "region", "type": "string", "value": "us-west-2"}
        ]
    }


@pytest.fixture
def sample_error_summary_event() -> Dict[str, Any]:
    """Sample event for query_error_summary function."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "sre-gold-tools",
        "function": "query_error_summary",
        "parameters": [
            {"name": "service", "type": "string", "value": "checkout-service"},
            {"name": "hours_back", "type": "integer", "value": "6"},
            {"name": "region", "type": "string", "value": "us-west-2"}
        ]
    }


@pytest.fixture
def sample_error_patterns_event() -> Dict[str, Any]:
    """Sample event for query_error_patterns function."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "sre-gold-tools",
        "function": "query_error_patterns",
        "parameters": [
            {"name": "service", "type": "string", "value": "checkout-service"}
        ]
    }


@pytest.fixture
def sample_historical_trend_event() -> Dict[str, Any]:
    """Sample event for query_historical_trend function."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "sre-gold-tools",
        "function": "query_historical_trend",
        "parameters": [
            {"name": "service", "type": "string", "value": "checkout-service"},
            {"name": "days_back", "type": "integer", "value": "7"}
        ]
    }


@pytest.fixture
def sample_dependencies_event() -> Dict[str, Any]:
    """Sample event for get_service_dependencies function."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "sre-gold-tools",
        "function": "get_service_dependencies",
        "parameters": [
            {"name": "service", "type": "string", "value": "checkout-service"}
        ]
    }


@pytest.fixture
def mock_lambda_context():
    """Mock Lambda context object."""
    context = Mock()
    context.function_name = "sre-gold-query-tools"
    context.function_version = "$LATEST"
    context.invoked_function_arn = "arn:aws:lambda:us-west-2:123456789012:function:sre-gold-query-tools"
    context.memory_limit_in_mb = "256"
    context.aws_request_id = "test-request-id-12345"
    context.log_group_name = "/aws/lambda/sre-gold-query-tools"
    context.log_stream_name = "2024/01/15/[$LATEST]test-stream"
    
    return context


@pytest.fixture
def sample_service_health_row():
    """Sample service health query result row."""
    return (
        "checkout-service",
        "us-west-2",
        75.0,
        "degraded",
        "2024-01-15 14:00:00"
    )


@pytest.fixture
def sample_error_summary_rows():
    """Sample error summary query result rows."""
    return [
        (
            "2024-01-15 14:00:00",
            "checkout-service",
            "us-west-2",
            342,
            45,
            2.5,
            True,
            "degrading",
            "High error rate detected: connection timeouts increased by 150%"
        ),
        (
            "2024-01-15 13:00:00",
            "checkout-service",
            "us-west-2",
            215,
            32,
            1.8,
            False,
            "stable",
            "Normal error levels"
        )
    ]


@pytest.fixture
def sample_error_pattern_rows():
    """Sample error pattern query result rows."""
    return [
        (
            "pattern-12345",
            "checkout-service",
            "ConnectionRefusedException",
            "connection_refused",
            "Connection refused to payment-gateway:8080",
            342,
            2.5,
            False,
            "Check payment-gateway service health and network connectivity",
            "2024-01-15 14:30:00"
        ),
        (
            "pattern-67890",
            "checkout-service",
            "TimeoutException",
            "timeout",
            "Request timeout after 30s",
            128,
            1.2,
            True,
            None,
            "2024-01-15 14:25:00"
        )
    ]


@pytest.fixture
def sample_historical_trend_rows():
    """Sample historical trend query result rows."""
    return [
        (
            "2024-01-15",
            "checkout-service",
            3542,
            1.8,
            True
        ),
        (
            "2024-01-14",
            "checkout-service",
            2156,
            1.2,
            False
        ),
        (
            "2024-01-13",
            "checkout-service",
            1987,
            1.0,
            False
        )
    ]


@pytest.fixture
def sample_dependency_rows():
    """Sample service dependency query result rows."""
    return [
        (
            "checkout-service",
            "payment-gateway",
            "synchronous",
            "HTTP"
        ),
        (
            "checkout-service",
            "inventory-service",
            "synchronous",
            "gRPC"
        ),
        (
            "order-service",
            "checkout-service",
            "async",
            "AMQP"
        )
    ]


@pytest.fixture(autouse=True)
def reset_credential_cache():
    """Reset the module-level credential cache between tests."""
    # Import handler module and reset cache
    import sys
    if 'handler' in sys.modules:
        import handler
        handler._DATABRICKS_TOKEN = None
    
    yield
    
    # Reset again after test
    if 'handler' in sys.modules:
        import handler
        handler._DATABRICKS_TOKEN = None
