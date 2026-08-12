"""
SRE Copilot — Local Development Server
=======================================
Runs the sre-chat-handler Lambda logic as a FastAPI server so you can use
the React UI locally with a real AWS Bedrock Agent and real Databricks SQL.

Requirements:
    pip install fastapi uvicorn boto3

Usage:
    # From sre-copilot/ directory:
    export AWS_REGION=us-west-2
    export AGENT_ID=<your-bedrock-agent-id>
    export AGENT_ALIAS_ID=<your-bedrock-agent-alias-id>
    python local_dev_server.py

    # Then start the UI in a second terminal:
    cd chat-ui
    VITE_API_URL=http://localhost:8000 npm run dev

The server proxies POST /chat → Bedrock Agent invoke_agent(), collecting
the streaming EventStream response before returning it to the browser.
Your local AWS credentials (from ~/.aws/credentials or environment variables)
are used — no Secrets Manager required for local dev.
"""

import json
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Optional

import boto3
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="SRE Copilot Local Dev Server", version="1.0.0")

# Allow all origins in dev — the Vite dev server runs on a different port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def validate_question(question: str) -> tuple[bool, Optional[str]]:
    if not question or not question.strip():
        return False, "Question cannot be empty"
    if len(question) > 2000:
        return False, "Question exceeds maximum length of 2000 characters"
    return True, None


def validate_session_id(session_id: str) -> tuple[bool, Optional[str]]:
    if not session_id or not session_id.strip():
        return False, "Session ID cannot be empty"
    parts = session_id.split("-")
    if len(parts) != 5:
        return False, "Invalid session ID format"
    if not (len(parts[0]) == 8 and len(parts[1]) == 4 and len(parts[2]) == 4
            and len(parts[3]) == 4 and len(parts[4]) == 12):
        return False, "Invalid session ID format"
    return True, None


def invoke_bedrock_agent(agent_id: str, agent_alias_id: str, session_id: str, input_text: str) -> tuple[str, str]:
    """
    Call the real AWS Bedrock Agent using local AWS credentials.
    Returns (full_response_text, data_freshness_iso_timestamp).
    """
    region = os.environ.get("AWS_REGION", "us-west-2")
    client = boto3.client("bedrock-agent-runtime", region_name=region)

    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=input_text,
    )

    full_response = ""
    for event in response.get("completion", []):
        if "chunk" in event:
            chunk_bytes = event["chunk"].get("bytes", b"")
            full_response += chunk_bytes.decode("utf-8")

    data_freshness = datetime.now(timezone.utc).isoformat()
    return full_response, data_freshness


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Quick sanity check — also verifies AWS credentials are configured."""
    agent_id = os.environ.get("AGENT_ID", "NOT SET")
    agent_alias_id = os.environ.get("AGENT_ALIAS_ID", "NOT SET")
    region = os.environ.get("AWS_REGION", "us-west-2")

    # Try listing Bedrock agents to verify credentials without side effects
    creds_ok = False
    creds_error = None
    try:
        sts = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        creds_ok = True
        account_id = identity["Account"]
    except Exception as e:
        creds_error = str(e)
        account_id = "unknown"

    return {
        "status": "ok",
        "agent_id_configured": agent_id != "NOT SET",
        "agent_alias_id_configured": agent_alias_id != "NOT SET",
        "aws_region": region,
        "aws_credentials_valid": creds_ok,
        "aws_account": account_id[-4:] + "****" if creds_ok else "unknown",  # only last 4 chars
        "creds_error": creds_error,
    }


@app.post("/chat")
async def chat(request: Request):
    """
    POST /chat { question: string, sessionId: string }
    → { response: string, sessionId: string, dataFreshness: string }

    Proxies the question to the real Bedrock Agent and returns the response.
    """
    start_time = time.time()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_json", "message": "Request body must be valid JSON"},
        )

    question = body.get("question", "")
    session_id = body.get("sessionId", "")

    print(f"[{datetime.now().isoformat()}] /chat  session={session_id[:8]}...  "
          f"question={question[:80]}{'...' if len(question) > 80 else ''}")

    # Validate inputs
    is_valid, error_msg = validate_question(question)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": "validation_error", "message": error_msg})

    is_valid, error_msg = validate_session_id(session_id)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": "validation_error", "message": error_msg})

    # Check env config
    agent_id = os.environ.get("AGENT_ID")
    agent_alias_id = os.environ.get("AGENT_ALIAS_ID")

    if not agent_id or not agent_alias_id:
        return JSONResponse(
            status_code=500,
            content={
                "error": "configuration_error",
                "message": (
                    "AGENT_ID and AGENT_ALIAS_ID environment variables are not set. "
                    "Run: export AGENT_ID=<id> AGENT_ALIAS_ID=<alias-id>"
                ),
            },
        )

    # Call real Bedrock Agent
    try:
        full_response, data_freshness = invoke_bedrock_agent(
            agent_id, agent_alias_id, session_id, question
        )
    except Exception as e:
        print("ERROR: Bedrock Agent invocation failed")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "error": "agent_invocation_failed",
                "message": f"Bedrock Agent error: {str(e)}",
            },
        )

    elapsed_ms = int((time.time() - start_time) * 1000)
    print(f"  → response_len={len(full_response)} chars  elapsed={elapsed_ms}ms")

    return JSONResponse(
        status_code=200,
        content={
            "response": full_response,
            "sessionId": session_id,
            "dataFreshness": data_freshness,
        },
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("=" * 60)
    print("  SRE Copilot — Local Dev Server")
    print("=" * 60)
    print(f"  API:      http://localhost:{port}")
    print(f"  Health:   http://localhost:{port}/health")
    print()
    print("  Required env vars:")
    print(f"    AGENT_ID        = {os.environ.get('AGENT_ID', '❌ NOT SET')}")
    print(f"    AGENT_ALIAS_ID  = {os.environ.get('AGENT_ALIAS_ID', '❌ NOT SET')}")
    print(f"    AWS_REGION      = {os.environ.get('AWS_REGION', 'us-west-2 (default)')}")
    print()
    print("  Start the UI in a second terminal:")
    print(f"    cd chat-ui && VITE_API_URL=http://localhost:{port} npm run dev")
    print("=" * 60)
    uvicorn.run("local_dev_server:app", host="0.0.0.0", port=port, reload=True)
