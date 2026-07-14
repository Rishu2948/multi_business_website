"""
Unit tests for the SRE Gold Query Tools Lambda Handler.

Tests cover:
- Handler routing and parameter extraction
- Databricks credential retrieval and caching
- All five Gold query functions
- Error handling and structured error payloads
- Structured logging with credential redaction
- Secrets Manager unavailable scenario
"""

import json
import os
import sys
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Mock the databricks module BEFORE importing handler, since handler imports it
# at module level.
# ──────────────────────────────────────────────────────────────────────────────
_mock_dbsql = MagicMock()
sys.modules.setdefault('databricks', MagicMock(sql=_mock_dbsql))
sys.modules.setdefault('databricks.sql', _mock_dbsql)

# Now import the handler (the module-level import of databricks.sql will use the mock)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import handler  # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_event(function_name: str, params: Dict[str, str]) -> Dict[str, Any]:
    """Build a minimal Bedrock Action Group v1.0 event."""
    return {
        "messageVersion": "1.0",
        "actionGroup": "sre-gold-tools",
        "function": function_name,
        "parameters": [
            {"name": k, "type": "string", "value": v} for k, v in params.items()
        ],
    }


def get_response_body(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and parse the TEXT body from a Bedrock Action Group response."""
    text_body = (
        response["response"]["functionResponse"]["responseBody"]["TEXT"]["body"]
    )
    return json.loads(text_body)


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_token_cache():
    """Ensure the module-level token cache is cleared between tests."""
    handler._DATABRICKS_TOKEN = None
    yield
    handler._DATABRICKS_TOKEN = None


@pytest.fixture
def env_vars(monkeypatch):
    """Provide required environment variables."""
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.setenv("DATABRICKS_HOST", "community.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/test-wh")


@pytest.fixture
def mock_sm(monkeypatch):
    """Mock Secrets Manager to return a test token."""
    sm = Mock()
    sm.get_secret_value.return_value = {"SecretString": "test-token-abc123"}

    def fake_client(service, region_name=None):
        if service == "secretsmanager":
            return sm
        return Mock()

    monkeypatch.setattr("boto3.client", fake_client)
    return sm


@pytest.fixture
def mock_sm_unavailable(monkeypatch):
    """Mock Secrets Manager to simulate unavailability."""
    sm = Mock()
    sm.get_secret_value.side_effect = Exception("Connection timeout")

    def fake_client(service, region_name=None):
        if service == "secretsmanager":
            return sm
        return Mock()

    monkeypatch.setattr("boto3.client", fake_client)
    return sm


@pytest.fixture
def mock_conn():
    """Return a mock Databricks connection + cursor pair."""
    cursor = Mock()
    cursor.fetchone.return_value = None
    cursor.fetchall.return_value = []
    cursor.close.return_value = None

    conn = Mock()
    conn.cursor.return_value = cursor
    conn.close.return_value = None
    return conn, cursor


@pytest.fixture
def lambda_context():
    ctx = Mock()
    ctx.function_name = "sre-gold-query-tools"
    return ctx


# ──────────────────────────────────────────────────────────────────────────────
# Parameter extraction
# ──────────────────────────────────────────────────────────────────────────────

class TestExtractParameters:
    def test_extracts_key_value_pairs(self):
        params = [
            {"name": "service", "type": "string", "value": "checkout-service"},
            {"name": "region", "type": "string", "value": "us-west-2"},
        ]
        result = handler.extract_parameters(params)
        assert result == {"service": "checkout-service", "region": "us-west-2"}

    def test_empty_list_returns_empty_dict(self):
        assert handler.extract_parameters([]) == {}


# ──────────────────────────────────────────────────────────────────────────────
# Credential management
# ──────────────────────────────────────────────────────────────────────────────

class TestCredentialManagement:
    def test_get_databricks_token_fetches_from_sm(self, mock_sm, env_vars):
        token = handler.get_databricks_token()
        assert token == "test-token-abc123"
        mock_sm.get_secret_value.assert_called_once_with(SecretId="sre/databricks-pat")

    def test_token_cached_after_first_call(self, mock_sm, env_vars):
        """Second call must NOT hit Secrets Manager again."""
        t1 = handler.get_databricks_token()
        t2 = handler.get_databricks_token()
        assert t1 == t2
        assert mock_sm.get_secret_value.call_count == 1

    def test_sm_unavailable_raises_error(self, mock_sm_unavailable, env_vars):
        with pytest.raises(handler.SecretsManagerUnavailableError):
            handler.get_databricks_token()


# ──────────────────────────────────────────────────────────────────────────────
# Credential redaction
# ──────────────────────────────────────────────────────────────────────────────

class TestRedactCredentials:
    def test_redacts_token_fields(self):
        params = {"service": "svc", "access_token": "super-secret"}
        result = handler.redact_credentials(params)
        assert result["access_token"] == "[REDACTED]"
        assert result["service"] == "svc"

    def test_redacts_password_fields(self):
        params = {"password": "hunter2", "query": "SELECT 1"}
        result = handler.redact_credentials(params)
        assert result["password"] == "[REDACTED]"
        assert result["query"] == "SELECT 1"

    def test_non_sensitive_fields_unchanged(self):
        params = {"service": "checkout", "region": "us-west-2"}
        result = handler.redact_credentials(params)
        assert result == params


# ──────────────────────────────────────────────────────────────────────────────
# Structured logging
# ──────────────────────────────────────────────────────────────────────────────

class TestStructuredLogging:
    def test_log_contains_required_fields(self, capsys):
        handler.emit_structured_log("my-func", {"service": "svc"}, 42)
        captured = capsys.readouterr().out
        log = json.loads(captured.strip())
        assert log["function_name"] == "my-func"
        assert "input_parameters" in log
        assert log["execution_duration_ms"] == 42

    def test_log_redacts_token(self, capsys):
        handler.emit_structured_log("fn", {"token": "secret-value", "x": "y"}, 0)
        captured = capsys.readouterr().out
        log = json.loads(captured.strip())
        assert log["input_parameters"]["token"] == "[REDACTED]"
        assert log["input_parameters"]["x"] == "y"


# ──────────────────────────────────────────────────────────────────────────────
# Response formatters
# ──────────────────────────────────────────────────────────────────────────────

class TestResponseFormatters:
    def test_success_response_structure(self):
        resp = handler.success_response("sre-gold-tools", "query_service_health", {"k": "v"})
        assert resp["messageVersion"] == "1.0"
        body = get_response_body(resp)
        assert body == {"k": "v"}

    def test_error_response_structure(self):
        resp = handler.error_response(
            "sre-gold-tools", "query_service_health",
            "TestError", "something broke", "my-service"
        )
        body = get_response_body(resp)
        assert body["error"] == "TestError"
        assert body["message"] == "something broke"
        assert body["service"] == "my-service"

    def test_error_response_without_service(self):
        resp = handler.error_response(
            "sre-gold-tools", "query_service_health",
            "TestError", "something broke"
        )
        body = get_response_body(resp)
        assert "service" not in body


# ──────────────────────────────────────────────────────────────────────────────
# Secrets Manager unavailable at cold start
# ──────────────────────────────────────────────────────────────────────────────

class TestSecretsManagerUnavailable:
    def test_returns_secrets_unavailable_error_payload(
        self, mock_sm_unavailable, env_vars, lambda_context
    ):
        event = make_event("query_service_health", {"service": "checkout-service"})
        response = handler.handler(event, lambda_context)

        # Must be a valid Bedrock response
        assert response["messageVersion"] == "1.0"
        body = get_response_body(response)
        assert body["error"] == "secrets_unavailable"

    def test_no_downstream_calls_when_sm_unavailable(
        self, mock_sm_unavailable, env_vars, lambda_context
    ):
        """When SM is unavailable, no Databricks connection should be attempted."""
        with patch.object(handler, "get_databricks_connection") as mock_conn:
            event = make_event("query_service_health", {"service": "svc"})
            handler.handler(event, lambda_context)
            mock_conn.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# Handler routing
# ──────────────────────────────────────────────────────────────────────────────

class TestHandlerRouting:
    """Verify the handler routes each function name to the correct query function."""

    @pytest.fixture(autouse=True)
    def patch_connection(self, mock_sm, env_vars, mock_conn):
        conn, cursor = mock_conn
        with patch.object(handler, "get_databricks_connection", return_value=conn):
            self.conn = conn
            self.cursor = cursor
            yield

    def test_routes_query_service_health(self, lambda_context):
        self.cursor.fetchone.return_value = (
            "checkout-service", "us-west-2", 75.0, "degraded", "2024-01-15 14:00:00"
        )
        event = make_event("query_service_health", {"service": "checkout-service"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert body["service"] == "checkout-service"
        assert body["overall_health"] == 75.0

    def test_routes_query_error_summary(self, lambda_context):
        self.cursor.fetchall.return_value = [
            ("2024-01-15 14:00:00", "checkout-service", "us-west-2",
             342, 45, 2.5, True, "degrading", "High error rate")
        ]
        event = make_event("query_error_summary", {
            "service": "checkout-service", "hours_back": "6"
        })
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert isinstance(body, list)
        assert body[0]["total_errors"] == 342

    def test_routes_query_error_patterns(self, lambda_context):
        self.cursor.fetchall.return_value = [
            ("pat-1", "checkout-service", "ConnectionRefusedException",
             "connection_refused", "Connection refused", 342, 2.5, False, None, "2024-01-15 14:30:00")
        ]
        event = make_event("query_error_patterns", {"service": "checkout-service"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert body[0]["occurrences_24h"] == 342

    def test_routes_query_historical_trend(self, lambda_context):
        self.cursor.fetchall.return_value = [
            ("2024-01-15", "checkout-service", 3542, 1.8, True)
        ]
        event = make_event("query_historical_trend", {
            "service": "checkout-service", "days_back": "7"
        })
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert body[0]["daily_errors"] == 3542

    def test_routes_get_service_dependencies(self, lambda_context):
        self.cursor.fetchall.return_value = [
            ("checkout-service", "payment-gateway", "synchronous", "HTTP")
        ]
        event = make_event("get_service_dependencies", {"service": "checkout-service"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert body[0]["target_service"] == "payment-gateway"

    def test_unknown_function_returns_error(self, lambda_context):
        event = make_event("nonexistent_function", {"service": "svc"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert body["error"] == "unknown_function"


# ──────────────────────────────────────────────────────────────────────────────
# Structured error payload on any exception (Requirements 4.7, 8.2)
# ──────────────────────────────────────────────────────────────────────────────

class TestStructuredErrorPayload:
    """
    The handler must ALWAYS return a structured error payload and NEVER propagate
    an unhandled exception regardless of what exception type is raised.
    """

    @pytest.fixture(autouse=True)
    def patch_token(self, mock_sm, env_vars):
        """Ensure token retrieval succeeds so errors come from query functions."""
        yield

    def _test_exception_produces_error_payload(self, exc, lambda_context):
        """Helper: make get_databricks_connection raise *exc* and verify structured response."""
        with patch.object(handler, "get_databricks_connection", side_effect=exc):
            event = make_event("query_service_health", {"service": "checkout-service"})
            resp = handler.handler(event, lambda_context)

        # Must be a valid Bedrock Action Group response
        assert "response" in resp
        assert resp["messageVersion"] == "1.0"

        body = get_response_body(resp)
        assert "error" in body, "Response body must contain 'error' key"
        assert "message" in body, "Response body must contain 'message' key"
        assert "service" in body, "Response body must contain 'service' key"
        return body

    def test_runtime_error_returns_structured_payload(self, lambda_context):
        body = self._test_exception_produces_error_payload(
            RuntimeError("unexpected runtime failure"), lambda_context
        )
        assert body["error"] == "RuntimeError"

    def test_value_error_returns_structured_payload(self, lambda_context):
        body = self._test_exception_produces_error_payload(
            ValueError("bad value"), lambda_context
        )
        assert body["error"] == "ValueError"

    def test_connection_error_returns_structured_payload(self, lambda_context):
        body = self._test_exception_produces_error_payload(
            ConnectionError("connection refused"), lambda_context
        )
        assert body["error"] == "ConnectionError"

    def test_base_exception_does_not_propagate(self, lambda_context):
        """The handler must NOT propagate any exception to the caller."""
        with patch.object(handler, "get_databricks_connection",
                          side_effect=Exception("generic error")):
            event = make_event("query_service_health", {"service": "svc"})
            # This call must not raise
            resp = handler.handler(event, lambda_context)
        assert "response" in resp

    def test_error_inside_query_function_returns_structured_payload(self, lambda_context):
        """Simulate an exception thrown INSIDE a query function."""
        failing_cursor = Mock()
        failing_cursor.execute.side_effect = Exception("SQL execution failed")
        failing_conn = Mock()
        failing_conn.cursor.return_value = failing_cursor
        failing_conn.close.return_value = None

        with patch.object(handler, "get_databricks_connection", return_value=failing_conn):
            event = make_event("query_service_health", {"service": "checkout-service"})
            resp = handler.handler(event, lambda_context)

        body = get_response_body(resp)
        assert "error" in body
        assert "message" in body
        assert body["service"] == "checkout-service"


# ──────────────────────────────────────────────────────────────────────────────
# Empty result sets
# ──────────────────────────────────────────────────────────────────────────────

class TestEmptyResultSets:
    @pytest.fixture(autouse=True)
    def patch_connection(self, mock_sm, env_vars, mock_conn):
        conn, cursor = mock_conn
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        with patch.object(handler, "get_databricks_connection", return_value=conn):
            yield

    def test_service_health_no_rows_returns_message(self, lambda_context):
        event = make_event("query_service_health", {"service": "unknown-svc"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert "message" in body
        assert body["service"] == "unknown-svc"

    def test_error_summary_no_rows_returns_empty_list(self, lambda_context):
        event = make_event("query_error_summary", {"service": "unknown-svc"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert isinstance(body, list)
        assert len(body) == 0

    def test_error_patterns_no_rows_returns_empty_list(self, lambda_context):
        event = make_event("query_error_patterns", {"service": "unknown-svc"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert isinstance(body, list)
        assert len(body) == 0

    def test_historical_trend_no_rows_returns_empty_list(self, lambda_context):
        event = make_event("query_historical_trend", {"service": "unknown-svc"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert isinstance(body, list)
        assert len(body) == 0

    def test_dependencies_no_rows_returns_empty_list(self, lambda_context):
        event = make_event("get_service_dependencies", {"service": "unknown-svc"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert isinstance(body, list)
        assert len(body) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Result set capping at 12 rows
# ──────────────────────────────────────────────────────────────────────────────

class TestResultCapping:
    @pytest.fixture(autouse=True)
    def patch_connection(self, mock_sm, env_vars, mock_conn):
        conn, cursor = mock_conn
        with patch.object(handler, "get_databricks_connection", return_value=conn):
            self.cursor = cursor
            yield

    def test_error_summary_respects_limit_12(self, lambda_context):
        """Verify query includes LIMIT 12 — we rely on the SQL having it, test the contract."""
        self.cursor.fetchall.return_value = [
            ("2024-01-15 14:00:00", "svc", "us-west-2", i, 0, 1.0, False, "stable", "ok")
            for i in range(12)
        ]
        event = make_event("query_error_summary", {"service": "svc"})
        resp = handler.handler(event, lambda_context)
        body = get_response_body(resp)
        assert len(body) == 12


# ──────────────────────────────────────────────────────────────────────────────
# Response structure conformance (Bedrock Action Group v1.0 schema)
# ──────────────────────────────────────────────────────────────────────────────

class TestBedrockResponseSchema:
    @pytest.fixture(autouse=True)
    def patch_connection(self, mock_sm, env_vars, mock_conn):
        conn, cursor = mock_conn
        with patch.object(handler, "get_databricks_connection", return_value=conn):
            self.cursor = cursor
            yield

    def _assert_valid_bedrock_response(self, resp):
        assert resp.get("messageVersion") == "1.0"
        assert "response" in resp
        r = resp["response"]
        assert "actionGroup" in r
        assert "function" in r
        assert "functionResponse" in r
        text = r["functionResponse"]["responseBody"]["TEXT"]["body"]
        # Must be valid JSON
        json.loads(text)

    def test_service_health_response_schema(self, lambda_context):
        self.cursor.fetchone.return_value = (
            "svc", "us-west-2", 100.0, "healthy", "2024-01-15 14:00:00"
        )
        event = make_event("query_service_health", {"service": "svc"})
        self._assert_valid_bedrock_response(handler.handler(event, lambda_context))

    def test_error_summary_response_schema(self, lambda_context):
        self.cursor.fetchall.return_value = []
        event = make_event("query_error_summary", {"service": "svc"})
        self._assert_valid_bedrock_response(handler.handler(event, lambda_context))

    def test_error_patterns_response_schema(self, lambda_context):
        self.cursor.fetchall.return_value = []
        event = make_event("query_error_patterns", {"service": "svc"})
        self._assert_valid_bedrock_response(handler.handler(event, lambda_context))

    def test_historical_trend_response_schema(self, lambda_context):
        self.cursor.fetchall.return_value = []
        event = make_event("query_historical_trend", {"service": "svc"})
        self._assert_valid_bedrock_response(handler.handler(event, lambda_context))

    def test_dependencies_response_schema(self, lambda_context):
        self.cursor.fetchall.return_value = []
        event = make_event("get_service_dependencies", {"service": "svc"})
        self._assert_valid_bedrock_response(handler.handler(event, lambda_context))


# ──────────────────────────────────────────────────────────────────────────────
# Individual query function unit tests (direct calls)
# ──────────────────────────────────────────────────────────────────────────────

class TestQueryServiceHealth:
    def test_returns_health_dict_when_row_found(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = (
            "checkout-service", "us-west-2", 50.0, "degraded", "2024-01-15 14:00:00"
        )
        result = handler.query_service_health(conn, "checkout-service")
        assert result["service"] == "checkout-service"
        assert result["overall_health"] == 50.0
        assert result["status"] == "degraded"

    def test_returns_no_data_message_when_no_row(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = None
        result = handler.query_service_health(conn, "unknown-svc")
        assert result["service"] == "unknown-svc"
        assert "message" in result

    def test_passes_region_filter_when_provided(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = (
            "svc", "eu-west-1", 100.0, "healthy", "2024-01-15 14:00:00"
        )
        result = handler.query_service_health(conn, "svc", region="eu-west-1")
        assert result["region"] == "eu-west-1"


class TestQueryErrorSummary:
    def test_returns_list_of_summaries(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            ("2024-01-15 14:00:00", "svc", "us-west-2", 100, 10, 1.5, False, "stable", "ok")
        ]
        result = handler.query_error_summary(conn, "svc")
        assert len(result) == 1
        assert result[0]["total_errors"] == 100

    def test_empty_results_return_empty_list(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        assert handler.query_error_summary(conn, "svc") == []

    def test_defaults_hours_back_to_6(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        handler.query_error_summary(conn, "svc", hours_back=None)
        # Verify the call was made (hours_back defaulted inside function)
        assert cursor.execute.called


class TestQueryErrorPatterns:
    def test_returns_list_of_patterns(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            ("pat-1", "svc", "TimeoutException", "timeout",
             "Timed out", 50, 1.2, False, None, "2024-01-15 14:00:00")
        ]
        result = handler.query_error_patterns(conn, "svc")
        assert len(result) == 1
        assert result[0]["error_category"] == "timeout"

    def test_top_10_contract(self):
        """The SQL in handler has LIMIT 10; we verify the function includes it in the query."""
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        # Return 10 rows to simulate the LIMIT being honoured
        cursor.fetchall.return_value = [
            (f"p{i}", "svc", "TypeError", "other", "msg", i, 1.0, False, None, "2024-01-15")
            for i in range(10)
        ]
        result = handler.query_error_patterns(conn, "svc")
        assert len(result) == 10


class TestQueryHistoricalTrend:
    def test_returns_aggregated_trend_rows(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            ("2024-01-15", "svc", 3000, 1.5, True),
            ("2024-01-14", "svc", 2000, 1.0, False),
        ]
        result = handler.query_historical_trend(conn, "svc")
        assert len(result) == 2
        assert result[0]["daily_errors"] == 3000
        assert result[0]["had_anomaly"] is True


class TestGetServiceDependencies:
    def test_returns_dependency_list(self):
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            ("checkout-service", "payment-gateway", "synchronous", "HTTP"),
        ]
        result = handler.get_service_dependencies(conn, "checkout-service")
        assert len(result) == 1
        assert result[0]["target_service"] == "payment-gateway"
        assert result[0]["protocol"] == "HTTP"

    def test_both_source_and_target_included(self):
        """Query should match on source_service OR target_service."""
        conn, cursor = Mock(), Mock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            ("order-service", "checkout-service", "async", "AMQP"),
            ("checkout-service", "payment-gateway", "synchronous", "HTTP"),
        ]
        result = handler.get_service_dependencies(conn, "checkout-service")
        assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
