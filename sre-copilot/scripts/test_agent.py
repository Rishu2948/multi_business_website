#!/usr/bin/env python3
"""test_agent.py

CLI end-to-end test for the SRE Copilot Bedrock Agent.

Invokes the live Agent with a sample SRE question, streams/collects the
full response, and validates that a non-empty structured response is returned.

Usage:
    python scripts/test_agent.py

Environment variables (required):
    AGENT_ID         – Bedrock Agent ID (exported as AgentId by stack 07-bedrock-agent).
    AGENT_ALIAS_ID   – Bedrock Agent Alias ID (exported as AgentAliasId by stack 07-bedrock-agent).

Optional:
    AWS_REGION       – AWS region (default: us-east-1).
    TEST_QUESTION    – Override the default sample question.
    SESSION_ID       – Override the auto-generated session UUID.

Exit codes:
    0  – Agent returned a non-empty response (test passed).
    1  – Test failed (missing env vars, API error, or empty response).

Requirements: 5.2, 9.1
"""

import logging
import os
import sys
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default test question — exercises the full investigation protocol
# ---------------------------------------------------------------------------
DEFAULT_QUESTION = "Why is checkout-service failing?"


def collect_agent_response(stream) -> str:
    """Read all chunks from a Bedrock Agent invoke_agent EventStream.

    The EventStream emits several event types; we only care about
    ``chunk`` events whose payload contains the text fragments.

    Args:
        stream: The ``EventStream`` object from ``invoke_agent`` response.

    Returns:
        The concatenated response text.

    Raises:
        RuntimeError: If the stream produces no text chunks at all.
    """
    fragments: list[str] = []

    for event in stream:
        # Each event is a dict with a single key identifying the event type.
        if "chunk" in event:
            chunk = event["chunk"]
            # The 'bytes' field is base64-decoded by boto3 automatically.
            fragment = chunk.get("bytes", b"").decode("utf-8", errors="replace")
            if fragment:
                fragments.append(fragment)
                logger.debug("Received chunk (%d chars)", len(fragment))
        elif "trace" in event:
            # Orchestration trace — useful for debugging but not part of the
            # answer; skip silently unless debug logging is enabled.
            trace = event["trace"].get("trace", {})
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Agent trace event: %s", trace)
        elif "returnControl" in event:
            # The Agent returned control to the caller (not expected in normal flow).
            logger.warning("Unexpected returnControl event: %s", event["returnControl"])
        elif "internalServerException" in event:
            raise RuntimeError(
                f"Bedrock Agent internal server error: {event['internalServerException']}"
            )
        elif "validationException" in event:
            raise RuntimeError(
                f"Bedrock Agent validation error: {event['validationException']}"
            )
        elif "resourceNotFoundException" in event:
            raise RuntimeError(
                f"Bedrock Agent resource not found: {event['resourceNotFoundException']}"
            )
        elif "serviceQuotaExceededException" in event:
            raise RuntimeError(
                f"Bedrock Agent quota exceeded: {event['serviceQuotaExceededException']}"
            )
        elif "throttlingException" in event:
            raise RuntimeError(
                f"Bedrock Agent request throttled: {event['throttlingException']}"
            )
        elif "accessDeniedException" in event:
            raise RuntimeError(
                f"Bedrock Agent access denied: {event['accessDeniedException']}"
            )
        else:
            # Unknown event type — log and continue rather than fail.
            logger.debug("Unknown event type in stream: %s", list(event.keys()))

    return "".join(fragments)


def run_test(agent_id: str, agent_alias_id: str, region: str) -> bool:
    """Invoke the Bedrock Agent and validate the response.

    Args:
        agent_id:       Bedrock Agent ID.
        agent_alias_id: Bedrock Agent Alias ID.
        region:         AWS region string.

    Returns:
        True if the test passed, False otherwise.
    """
    question = os.environ.get("TEST_QUESTION", DEFAULT_QUESTION).strip()
    session_id = os.environ.get("SESSION_ID", str(uuid.uuid4()))

    logger.info("=" * 60)
    logger.info("SRE Copilot Agent — End-to-End Test")
    logger.info("=" * 60)
    logger.info("Region       : %s", region)
    logger.info("Agent ID     : %s", agent_id)
    logger.info("Alias ID     : %s", agent_alias_id)
    logger.info("Session ID   : %s", session_id)
    logger.info("Question     : %s", question)
    logger.info("-" * 60)

    client = boto3.client("bedrock-agent-runtime", region_name=region)

    try:
        logger.info("Invoking agent …")
        api_response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=question,
            # enableTrace=True,  # Uncomment for verbose orchestration tracing
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error("invoke_agent ClientError [%s]: %s", error_code, error_msg)
        return False
    except BotoCoreError as exc:
        logger.error("boto3 BotoCoreError: %s", exc)
        return False

    # Collect the streaming response
    try:
        event_stream = api_response.get("completion")
        if event_stream is None:
            logger.error(
                "invoke_agent response did not contain 'completion' key. "
                "Response keys: %s",
                list(api_response.keys()),
            )
            return False

        response_text = collect_agent_response(event_stream)
    except RuntimeError as exc:
        logger.error("Error reading agent response stream: %s", exc)
        return False

    logger.info("-" * 60)

    # -----------------------------------------------------------------------
    # Validation: the response must be a non-empty string
    # -----------------------------------------------------------------------
    if not response_text:
        logger.error(
            "FAIL: Agent returned an empty response. "
            "Check that the Agent is prepared and the Alias points to a deployed version."
        )
        return False

    logger.info("Agent response (%d chars):", len(response_text))
    logger.info("")
    # Print the full response to stdout for inspection
    print("\n" + "=" * 60)
    print("AGENT RESPONSE")
    print("=" * 60)
    print(response_text)
    print("=" * 60 + "\n")

    logger.info("PASS: Agent returned a non-empty structured response.")
    return True


def main() -> None:
    """Entry point: validate env vars, run the test, exit with appropriate code."""

    # -----------------------------------------------------------------------
    # Validate required environment variables
    # -----------------------------------------------------------------------
    agent_id = os.environ.get("AGENT_ID", "").strip()
    agent_alias_id = os.environ.get("AGENT_ALIAS_ID", "").strip()
    region = os.environ.get("AWS_REGION", "us-east-1").strip()

    missing: list[str] = []
    if not agent_id:
        missing.append("AGENT_ID")
    if not agent_alias_id:
        missing.append("AGENT_ALIAS_ID")

    if missing:
        logger.error(
            "Required environment variable(s) not set: %s",
            ", ".join(missing),
        )
        logger.error(
            "Retrieve them from CloudFormation stack outputs:\n"
            "  aws cloudformation describe-stacks --stack-name sre-bedrock-agent "
            "--query 'Stacks[0].Outputs'"
        )
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Run the test
    # -----------------------------------------------------------------------
    passed = run_test(agent_id, agent_alias_id, region)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
