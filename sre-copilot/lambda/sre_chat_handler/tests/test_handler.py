"""
Unit tests for the SRE Chat Handler Lambda function.

Tests cover:
- CORS preflight handling
- Input validation (question and sessionId)
- Successful agent invocation
- Error handling for various failure scenarios
"""

import json
import os
from unittest.mock import MagicMock, patch, Mock

import pytest

# Import the handler module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from handler import (
    handler,
    cors_preflight_response,
    validate_question,
    validate_session_id,
    invoke_bedrock_agent,
    emit_structured_log,
    error_response,
    success_response
)


# Test Fixtures
@pytest.fixture
def valid_session_id():
    """Return a valid UUID session ID."""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def valid_question():
    """Return a valid question."""
    return "Why is checkout-service failing?"


@pytest.fixture
def api_gateway_event(valid_question, valid_session_id):
    """Create a valid API Gateway proxy event."""
    return {
        'httpMethod': 'POST',
        'body': json.dumps({
            'question': valid_question,
            'sessionId': valid_session_id
        }),
        'headers': {
            'Content-Type': 'application/json'
        }
    }


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context object."""
    context = MagicMock()
    context.function_name = 'sre-chat-handler'
    context.memory_limit_in_mb = 256
    context.invoked_function_arn = 'arn:aws:lambda:us-west-2:123456789012:function:sre-chat-handler'
    return context


# CORS Tests
class TestCORS:
    """Test CORS functionality."""
    
    def test_options_request_returns_200(self, lambda_context):
        """Test that OPTIONS request returns 200 with CORS headers."""
        event = {
            'httpMethod': 'OPTIONS',
            'headers': {}
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        assert 'Access-Control-Allow-Methods' in response['headers']
        assert 'Access-Control-Allow-Headers' in response['headers']
    
    def test_cors_headers_present_in_all_responses(self, api_gateway_event, lambda_context):
        """Test that CORS headers are present in all responses."""
        # Mock environment variables
        with patch.dict(os.environ, {'AGENT_ID': 'test-agent', 'AGENT_ALIAS_ID': 'test-alias'}):
            with patch('handler.invoke_bedrock_agent') as mock_invoke:
                mock_invoke.return_value = ("Test response", "2024-01-15T14:30:00Z")
                
                response = handler(api_gateway_event, lambda_context)
                
                assert 'Access-Control-Allow-Origin' in response['headers']
                assert 'Access-Control-Allow-Methods' in response['headers']


# Validation Tests
class TestValidation:
    """Test input validation."""
    
    def test_empty_question_returns_400(self, valid_session_id, lambda_context):
        """Test that empty question returns 400 error."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': '',
                'sessionId': valid_session_id
            })
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'validation_error'
        assert 'empty' in body['message'].lower()
    
    def test_whitespace_only_question_returns_400(self, valid_session_id, lambda_context):
        """Test that whitespace-only question returns 400 error."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': '   ',
                'sessionId': valid_session_id
            })
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'validation_error'
    
    def test_question_exceeds_max_length_returns_400(self, valid_session_id, lambda_context):
        """Test that question exceeding 2000 characters returns 400 error."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': 'a' * 2001,
                'sessionId': valid_session_id
            })
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'validation_error'
        assert '2000' in body['message']
    
    def test_question_exactly_2000_chars_is_valid(self, valid_session_id, lambda_context):
        """Test that question with exactly 2000 characters is valid."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': 'a' * 2000,
                'sessionId': valid_session_id
            })
        }
        
        with patch.dict(os.environ, {'AGENT_ID': 'test-agent', 'AGENT_ALIAS_ID': 'test-alias'}):
            with patch('handler.invoke_bedrock_agent') as mock_invoke:
                mock_invoke.return_value = ("Test response", "2024-01-15T14:30:00Z")
                
                response = handler(event, lambda_context)
                
                # Should not be a validation error
                assert response['statusCode'] != 400 or json.loads(response['body'])['error'] != 'validation_error'
    
    def test_empty_session_id_returns_400(self, valid_question, lambda_context):
        """Test that empty session ID returns 400 error."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': valid_question,
                'sessionId': ''
            })
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'validation_error'
        assert 'session' in body['message'].lower()
    
    def test_invalid_session_id_format_returns_400(self, valid_question, lambda_context):
        """Test that invalid session ID format returns 400 error."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': valid_question,
                'sessionId': 'not-a-valid-uuid'
            })
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'validation_error'
    
    def test_invalid_json_body_returns_400(self, lambda_context):
        """Test that invalid JSON body returns 400 error."""
        event = {
            'httpMethod': 'POST',
            'body': 'not-valid-json{{'
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] == 'invalid_json'


# Validation Helper Function Tests
class TestValidationHelpers:
    """Test validation helper functions directly."""
    
    def test_validate_question_success(self):
        """Test validate_question with valid input."""
        is_valid, error = validate_question("Why is the service down?")
        assert is_valid is True
        assert error is None
    
    def test_validate_question_empty(self):
        """Test validate_question with empty input."""
        is_valid, error = validate_question("")
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_validate_question_too_long(self):
        """Test validate_question with input exceeding max length."""
        is_valid, error = validate_question("x" * 2001)
        assert is_valid is False
        assert "2000" in error
    
    def test_validate_session_id_success(self):
        """Test validate_session_id with valid UUID."""
        is_valid, error = validate_session_id("550e8400-e29b-41d4-a716-446655440000")
        assert is_valid is True
        assert error is None
    
    def test_validate_session_id_invalid_format(self):
        """Test validate_session_id with invalid format."""
        is_valid, error = validate_session_id("not-a-uuid")
        assert is_valid is False
        assert "format" in error.lower()


# Success Path Tests
class TestSuccessPath:
    """Test successful agent invocation scenarios."""
    
    @patch('handler.invoke_bedrock_agent')
    def test_successful_invocation_returns_200(self, mock_invoke, api_gateway_event, lambda_context):
        """Test that successful agent invocation returns 200 with response."""
        mock_invoke.return_value = (
            "checkout-service is experiencing connection timeouts...",
            "2024-01-15T14:30:00Z"
        )
        
        with patch.dict(os.environ, {'AGENT_ID': 'test-agent', 'AGENT_ALIAS_ID': 'test-alias'}):
            response = handler(api_gateway_event, lambda_context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'response' in body
        assert 'sessionId' in body
        assert 'dataFreshness' in body
        assert body['response'] == "checkout-service is experiencing connection timeouts..."
        assert body['sessionId'] == "550e8400-e29b-41d4-a716-446655440000"
        assert body['dataFreshness'] == "2024-01-15T14:30:00Z"
    
    @patch('handler.invoke_bedrock_agent')
    def test_session_id_preserved_in_response(self, mock_invoke, valid_question, lambda_context):
        """Test that session ID is preserved in the response."""
        session_id = "12345678-1234-1234-1234-123456789012"
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': valid_question,
                'sessionId': session_id
            })
        }
        
        mock_invoke.return_value = ("Test response", "2024-01-15T14:30:00Z")
        
        with patch.dict(os.environ, {'AGENT_ID': 'test-agent', 'AGENT_ALIAS_ID': 'test-alias'}):
            response = handler(event, lambda_context)
        
        body = json.loads(response['body'])
        assert body['sessionId'] == session_id


# Error Handling Tests
class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_missing_agent_id_returns_500(self, api_gateway_event, lambda_context):
        """Test that missing AGENT_ID environment variable returns 500."""
        with patch.dict(os.environ, {'AGENT_ALIAS_ID': 'test-alias'}, clear=True):
            response = handler(api_gateway_event, lambda_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'configuration_error'
    
    def test_missing_agent_alias_id_returns_500(self, api_gateway_event, lambda_context):
        """Test that missing AGENT_ALIAS_ID environment variable returns 500."""
        with patch.dict(os.environ, {'AGENT_ID': 'test-agent'}, clear=True):
            response = handler(api_gateway_event, lambda_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'configuration_error'
    
    @patch('handler.invoke_bedrock_agent')
    def test_agent_invocation_failure_returns_500(self, mock_invoke, api_gateway_event, lambda_context):
        """Test that agent invocation failure returns 500."""
        mock_invoke.side_effect = Exception("Agent timeout")
        
        with patch.dict(os.environ, {'AGENT_ID': 'test-agent', 'AGENT_ALIAS_ID': 'test-alias'}):
            response = handler(api_gateway_event, lambda_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'agent_invocation_failed'
        assert 'Agent timeout' in body['message']
    
    @patch('handler.boto3.client')
    def test_bedrock_client_error(self, mock_boto_client, valid_question, valid_session_id, lambda_context):
        """Test handling of Bedrock client errors."""
        mock_client = Mock()
        mock_client.invoke_agent.side_effect = Exception("Service unavailable")
        mock_boto_client.return_value = mock_client
        
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': valid_question,
                'sessionId': valid_session_id
            })
        }
        
        with patch.dict(os.environ, {'AGENT_ID': 'test-agent', 'AGENT_ALIAS_ID': 'test-alias'}):
            response = handler(event, lambda_context)
        
        assert response['statusCode'] == 500
        body = json.loads(response['body'])
        assert body['error'] == 'agent_invocation_failed'


# Bedrock Agent Invocation Tests
class TestBedrockAgentInvocation:
    """Test Bedrock Agent invocation logic."""
    
    @patch('handler.boto3.client')
    def test_invoke_bedrock_agent_collects_streaming_response(self, mock_boto_client):
        """Test that invoke_bedrock_agent correctly collects streaming chunks."""
        # Mock streaming response
        mock_client = Mock()
        mock_response = {
            'completion': [
                {'chunk': {'bytes': b'First chunk. '}},
                {'chunk': {'bytes': b'Second chunk. '}},
                {'chunk': {'bytes': b'Third chunk.'}}
            ]
        }
        mock_client.invoke_agent.return_value = mock_response
        mock_boto_client.return_value = mock_client
        
        full_response, data_freshness = invoke_bedrock_agent(
            'test-agent',
            'test-alias',
            'test-session-id',
            'Test question'
        )
        
        assert full_response == 'First chunk. Second chunk. Third chunk.'
        assert data_freshness is not None
    
    @patch('handler.boto3.client')
    def test_invoke_bedrock_agent_handles_empty_stream(self, mock_boto_client):
        """Test that invoke_bedrock_agent handles empty event stream."""
        mock_client = Mock()
        mock_response = {'completion': []}
        mock_client.invoke_agent.return_value = mock_response
        mock_boto_client.return_value = mock_client
        
        full_response, data_freshness = invoke_bedrock_agent(
            'test-agent',
            'test-alias',
            'test-session-id',
            'Test question'
        )
        
        assert full_response == ''
        assert data_freshness is not None
    
    @patch('handler.boto3.client')
    def test_invoke_bedrock_agent_passes_correct_parameters(self, mock_boto_client):
        """Test that invoke_bedrock_agent passes correct parameters to boto3."""
        mock_client = Mock()
        mock_response = {'completion': []}
        mock_client.invoke_agent.return_value = mock_response
        mock_boto_client.return_value = mock_client
        
        invoke_bedrock_agent(
            'my-agent-id',
            'my-alias-id',
            'my-session-id',
            'My test question'
        )
        
        mock_client.invoke_agent.assert_called_once_with(
            agentId='my-agent-id',
            agentAliasId='my-alias-id',
            sessionId='my-session-id',
            inputText='My test question'
        )


# Logging Tests
class TestLogging:
    """Test structured logging functionality."""
    
    @patch('builtins.print')
    def test_emit_structured_log_format(self, mock_print):
        """Test that emit_structured_log outputs correct JSON format."""
        emit_structured_log(
            'test-function',
            {'param1': 'value1', 'param2': 'value2'},
            123
        )
        
        # Verify print was called
        assert mock_print.called
        
        # Parse the logged JSON
        logged_str = mock_print.call_args[0][0]
        logged_data = json.loads(logged_str)
        
        assert logged_data['function_name'] == 'test-function'
        assert logged_data['input_parameters']['param1'] == 'value1'
        assert logged_data['execution_duration_ms'] == 123
    
    @patch('builtins.print')
    def test_long_questions_truncated_in_logs(self, mock_print):
        """Test that long questions are truncated in log output."""
        long_question = 'a' * 200
        
        emit_structured_log(
            'test-function',
            {'question': long_question},
            100
        )
        
        logged_str = mock_print.call_args[0][0]
        logged_data = json.loads(logged_str)
        
        # Question should be truncated to 100 chars + "..."
        assert len(logged_data['input_parameters']['question']) == 103
        assert logged_data['input_parameters']['question'].endswith('...')


# Response Helper Tests
class TestResponseHelpers:
    """Test response formatting helper functions."""
    
    def test_error_response_format(self):
        """Test error_response formatting."""
        response = error_response(400, 'test_error', 'Test error message')
        
        assert response['statusCode'] == 400
        assert 'Access-Control-Allow-Origin' in response['headers']
        
        body = json.loads(response['body'])
        assert body['error'] == 'test_error'
        assert body['message'] == 'Test error message'
    
    def test_success_response_format(self):
        """Test success_response formatting."""
        response = success_response(
            'Test response text',
            'test-session-id',
            '2024-01-15T14:30:00Z'
        )
        
        assert response['statusCode'] == 200
        assert 'Access-Control-Allow-Origin' in response['headers']
        
        body = json.loads(response['body'])
        assert body['response'] == 'Test response text'
        assert body['sessionId'] == 'test-session-id'
        assert body['dataFreshness'] == '2024-01-15T14:30:00Z'
    
    def test_success_response_without_data_freshness(self):
        """Test success_response without data freshness."""
        response = success_response(
            'Test response text',
            'test-session-id'
        )
        
        body = json.loads(response['body'])
        assert 'dataFreshness' not in body


# Integration Tests
class TestIntegration:
    """Integration-style tests for complete request flow."""
    
    @patch('handler.invoke_bedrock_agent')
    def test_complete_successful_flow(self, mock_invoke, lambda_context):
        """Test complete successful request-response flow."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': 'What is the status of payment-service?',
                'sessionId': '12345678-1234-1234-1234-123456789012'
            })
        }
        
        mock_invoke.return_value = (
            "payment-service is healthy with no recent errors.",
            "2024-01-15T15:00:00Z"
        )
        
        with patch.dict(os.environ, {'AGENT_ID': 'agent-123', 'AGENT_ALIAS_ID': 'alias-456'}):
            response = handler(event, lambda_context)
        
        assert response['statusCode'] == 200
        
        body = json.loads(response['body'])
        assert body['response'] == "payment-service is healthy with no recent errors."
        assert body['sessionId'] == '12345678-1234-1234-1234-123456789012'
        assert body['dataFreshness'] == "2024-01-15T15:00:00Z"
        
        # Verify CORS headers
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
    
    @patch('handler.invoke_bedrock_agent')
    def test_error_flow_preserves_cors(self, mock_invoke, lambda_context):
        """Test that error responses still include CORS headers."""
        event = {
            'httpMethod': 'POST',
            'body': json.dumps({
                'question': '',  # Invalid: empty question
                'sessionId': '12345678-1234-1234-1234-123456789012'
            })
        }
        
        response = handler(event, lambda_context)
        
        assert response['statusCode'] == 400
        assert 'Access-Control-Allow-Origin' in response['headers']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
