"""
ai-chatbot/services/nl_processor.py

NL Processor — calls the configured LLM API to extract structured intent
from a natural-language user message and returns a normalised result dict.

Supported providers (``LLM_PROVIDER`` env var):
  - ``openai``    — POST https://api.openai.com/v1/chat/completions
  - ``anthropic`` — POST https://api.anthropic.com/v1/messages
  - ``bedrock``   — AWS Bedrock Runtime (boto3); auth via IAM role — no API key needed.
                    Set LLM_MODEL to a Bedrock model ID, e.g.:
                      anthropic.claude-3-haiku-20240307-v1:0  (recommended — fast, cheap)
                      anthropic.claude-3-sonnet-20240229-v1:0
                      amazon.titan-text-express-v1
                    Bedrock uses the ECS task role for auth; ensure the task role has
                    the bedrock:InvokeModel permission on the chosen model ARN.

Requirements: 2.1, 2.2, 3.1, 3.2, 6.7, 9.3, 9.6
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Spec-defined fallback response text (Req 6.7, 9.3)
FALLBACK_RESPONSE = (
    "I'm sorry, I couldn't process your request. "
    "Please try browsing the catalog manually or contact support."
)

# Confidence below this threshold forces a "clarify" intent (Req 2.2 / design)
_CONFIDENCE_THRESHOLD: float = 0.6

# Intents that are out-of-scope for catalog interaction (Req 9.6)
# These are intents that should be declined regardless of LLM output
_OUT_OF_SCOPE_INTENTS: frozenset[str] = frozenset(
    {"add_to_cart", "place_order", "change_password"}
)

# Prompt-injection detection pattern (Req 9.3)
# Matches: "ignore previous/all/prior", "override system", "you are now"
_INJECTION_RE = re.compile(
    r"ignore\s+(previous|all|prior)|override\s+system|you\s+are\s+now",
    re.IGNORECASE,
)

# Out-of-scope decline message
_OUT_OF_SCOPE_REPLY = (
    "I can only help you discover products in this catalog. "
    "For orders, account changes, and other actions please use the website directly."
)

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _env(key: str, default: str = "") -> str:
    """Return the value of an environment variable, stripping whitespace."""
    return os.environ.get(key, default).strip()


def _timeout() -> float:
    """Parse ``LLM_TIMEOUT_SECONDS`` env var; default 8.0 seconds."""
    try:
        return float(_env("LLM_TIMEOUT_SECONDS", "8"))
    except ValueError:
        return 8.0


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def _build_system_prompt(business_name: str) -> str:
    """Return the structured JSON-only system prompt for the LLM."""
    biz_label = business_name or "this business"
    return f"""You are a product catalog assistant for {biz_label}.
Your ONLY job is to parse the user's latest message and return a JSON object.

CRITICAL RULES — you MUST follow these exactly:
1. Output ONLY a single raw JSON object. No markdown, no backticks, no prose, no explanation.
2. The JSON must have exactly these keys: intent, filters, confidence_score, reply
3. Do NOT copy or repeat previous assistant messages. Ignore prior conversation tone.
4. Even if prior turns show prose responses, YOU must output JSON — always.

JSON schema:
{{
  "intent": "search|filter|recommend|compare|clarify|out_of_scope|clear_filters",
  "filters": {{
    "keyword": "<string or null>",
    "category": "<string or null>",
    "price_min": "<number or null>",
    "price_max": "<number or null>",
    "flavor": "<string or null>",
    "occasion": "<string or null>"
  }},
  "confidence_score": <float 0.0-1.0>,
  "reply": "<one sentence natural language reply>"
}}

Intent rules:
- "search"        — user wants to find products (NEW search, replaces all prior filters)
- "filter"        — user is REFINING the current results by adding/changing a filter
- "clear_filters" — user says "clear", "reset", "start over", "remove filters" etc.
- "recommend"     — user wants a recommendation
- "compare"       — user wants to compare products
- "clarify"       — confidence_score < 0.6 or request is ambiguous
- "out_of_scope"  — add_to_cart, place_order, change_password, non-catalog actions

Filter rules:
- For "search" intent: set all relevant filters, set unrelated ones to null
- For "filter" intent: only set the filters being changed, leave others null
- For "clear_filters" intent: set ALL filter values to null
- A null value means "remove this filter"

Examples of valid output:
{{"intent":"search","filters":{{"keyword":"chocolate cheesecake","flavor":"chocolate","category":null,"price_min":null,"price_max":null,"occasion":null}},"confidence_score":0.95,"reply":"Here are the chocolate cheesecake options."}}
{{"intent":"search","filters":{{"keyword":"truffle cake","flavor":null,"category":null,"price_min":null,"price_max":null,"occasion":null}},"confidence_score":0.95,"reply":"Here are the truffle cake options."}}
{{"intent":"clear_filters","filters":{{"keyword":null,"category":null,"price_min":null,"price_max":null,"flavor":null,"occasion":null}},"confidence_score":0.99,"reply":"All filters cleared. What would you like to search for?"}}

Never output anything except the JSON object — no text before or after it."""


# ---------------------------------------------------------------------------
# LLM API call helpers
# ---------------------------------------------------------------------------


async def _call_openai(
    client: httpx.AsyncClient,
    messages: list[dict],
) -> str:
    """Call the OpenAI chat completions endpoint and return the raw content."""
    api_key = _env("LLM_API_KEY")
    model = _env("LLM_MODEL", "gpt-4o-mini")

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    response = await client.post(
        "https://api.openai.com/v1/chat/completions",
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


async def _call_anthropic(
    client: httpx.AsyncClient,
    system_prompt: str,
    messages: list[dict],
) -> str:
    """Call the Anthropic messages endpoint and return the raw content."""
    api_key = _env("LLM_API_KEY")
    model = _env("LLM_MODEL", "claude-3-haiku-20240307")

    # Anthropic separates the system prompt from the message array
    # and only accepts "user"/"assistant" roles.
    anthropic_messages = [m for m in messages if m["role"] in ("user", "assistant")]

    payload: dict[str, Any] = {
        "model": model,
        "system": system_prompt,
        "messages": anthropic_messages,
        "max_tokens": 512,
    }
    response = await client.post(
        "https://api.anthropic.com/v1/messages",
        json=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()
    data = response.json()
    return data["content"][0]["text"]


def _call_bedrock(
    system_prompt: str,
    messages: list[dict],
) -> str:
    """Call AWS Bedrock Runtime ``InvokeModel`` and return the raw content string.

    Auth is handled by the IAM role attached to the ECS task — no API key is
    required. Ensure the task role has ``bedrock:InvokeModel`` on the model ARN.

    Supports Claude-on-Bedrock model IDs (anthropic.*) and Amazon Titan
    (amazon.titan-text-express-v1). Falls back to the Titan request shape for
    unknown model IDs.

    This is a synchronous boto3 call. The caller wraps it in
    ``asyncio.to_thread`` so it doesn't block the event loop.
    """
    import boto3  # imported lazily — only needed when LLM_PROVIDER=bedrock

    model_id = _env("LLM_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
    region = _env("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

    client = boto3.client("bedrock-runtime", region_name=region)

    # ── Claude-on-Bedrock ────────────────────────────────────────────────────
    if model_id.startswith("anthropic."):
        # Anthropic on Bedrock uses the Messages API with anthropic_version header
        anthropic_messages = [
            m for m in messages if m["role"] in ("user", "assistant")
        ]
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "system": system_prompt,
                "messages": anthropic_messages,
                "max_tokens": 512,
                "temperature": 0.2,
            }
        )
        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    # ── Amazon Nova Text ─────────────────────────────────────────────────────
    if model_id.startswith("amazon.nova"):
        # Nova uses the Converse API shape
        nova_messages = [
            {"role": m["role"], "content": [{"text": m["content"]}]}
            for m in messages
            if m["role"] in ("user", "assistant")
        ]
        body = json.dumps(
            {
                "system": [{"text": system_prompt}],
                "messages": nova_messages,
                "inferenceConfig": {
                    "maxTokens": 512,
                    "temperature": 0.2,
                },
            }
        )
        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"]

    # ── Amazon Titan Text ────────────────────────────────────────────────────
    if model_id.startswith("amazon.titan-text"):
        # Build a single text prompt by concatenating system + user turns
        prompt_parts = [f"System: {system_prompt}"]
        for m in messages:
            role_label = "User" if m["role"] == "user" else "Assistant"
            prompt_parts.append(f"{role_label}: {m['content']}")
        prompt_parts.append("Assistant:")  # signal the model to respond
        full_prompt = "\n\n".join(prompt_parts)

        body = json.dumps(
            {
                "inputText": full_prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 512,
                    "temperature": 0.2,
                    "topP": 0.9,
                },
            }
        )
        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["results"][0]["outputText"]

    # ── Meta Llama (amazon.meta.*) ───────────────────────────────────────────
    if model_id.startswith("meta."):
        prompt_parts = [f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n"]
        for m in messages:
            if m["role"] == "user":
                prompt_parts.append(f"{m['content']} [/INST] ")
            elif m["role"] == "assistant":
                prompt_parts.append(f"{m['content']} </s><s>[INST] ")
        full_prompt = "".join(prompt_parts)

        body = json.dumps(
            {
                "prompt": full_prompt,
                "max_gen_len": 512,
                "temperature": 0.2,
                "top_p": 0.9,
            }
        )
        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        return result["generation"]

    # ── Unknown model — attempt Claude-style payload as best-effort ──────────
    logger.warning("Unknown Bedrock model ID '%s'; attempting Claude-style payload.", model_id)
    anthropic_messages = [m for m in messages if m["role"] in ("user", "assistant")]
    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "system": system_prompt,
            "messages": anthropic_messages,
            "max_tokens": 512,
        }
    )
    response = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["content"][0]["text"]


# ---------------------------------------------------------------------------
# Prompt-injection detection
# ---------------------------------------------------------------------------


def _check_injection(payload: dict, client_ip: str) -> bool:
    """Return ``True`` if any string field in ``payload`` contains an injection pattern.

    Checked fields: all top-level string values and nested string values inside
    ``filters``. On detection, the incident is logged with the current UTC
    timestamp and the caller's IP address (Req 9.3).
    """
    # Collect all string values to check
    candidates: list[str] = []

    for key, value in payload.items():
        if isinstance(value, str):
            candidates.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                if isinstance(v, str):
                    candidates.append(v)

    for text in candidates:
        if _INJECTION_RE.search(text):
            timestamp = datetime.now(timezone.utc).isoformat()
            logger.warning(
                "Prompt injection detected | timestamp=%s ip=%s pattern_matched=%r",
                timestamp,
                client_ip,
                text[:120],  # truncate to avoid log flooding
            )
            return True

    return False


# ---------------------------------------------------------------------------
# Response normalisation
# ---------------------------------------------------------------------------


def _normalise(raw_json: dict, active_filters: dict) -> dict:
    """Normalise the LLM JSON envelope into the standard return shape.

    Business rules:
    - confidence_score < 0.6 → intent = "clarify"
    - clear_filters intent → wipe active_filters entirely
    - search intent → REPLACE active_filters with new filters (not merge)
    - filter intent → MERGE: new filters override, null values remove the key
    - Null filter values from LLM explicitly remove that key from active_filters
    """
    confidence: float = float(raw_json.get("confidence_score", 0.0))
    intent: str = str(raw_json.get("intent", "clarify")).strip().lower()
    reply: str = str(raw_json.get("reply", FALLBACK_RESPONSE)).strip()

    # Confidence threshold check (Req 2.2)
    if confidence < _CONFIDENCE_THRESHOLD:
        intent = "clarify"
        reply = FALLBACK_RESPONSE

    raw_filters: dict = raw_json.get("filters") or {}

    # clear_filters: wipe everything
    if intent == "clear_filters":
        return {
            "intent": "clear_filters",
            "filters": {},
            "active_filters": {},
            "confidence_score": confidence,
            "reply": reply,
        }

    # Separate explicitly-set filters from null ones
    new_filters = {k: v for k, v in raw_filters.items() if v is not None}
    null_keys = {k for k, v in raw_filters.items() if v is None}

    if intent == "search":
        # New search: start fresh with only the new filters
        # This prevents old filters (e.g. flavor:chocolate) bleeding into a new query
        merged_filters = dict(new_filters)
    else:
        # filter/recommend/compare: merge — new values override, null values remove
        merged_filters = {k: v for k, v in active_filters.items() if k not in null_keys}
        merged_filters.update(new_filters)

    return {
        "intent": intent,
        "filters": new_filters,
        "active_filters": merged_filters,
        "confidence_score": confidence,
        "reply": reply,
    }


# ---------------------------------------------------------------------------
# Fallback result builder
# ---------------------------------------------------------------------------


def _fallback_result(active_filters: dict) -> dict:
    """Return a safe fallback result dict with ``clarify`` intent."""
    return {
        "intent": "clarify",
        "filters": {},
        "active_filters": active_filters,
        "confidence_score": 0.0,
        "reply": FALLBACK_RESPONSE,
    }


# ---------------------------------------------------------------------------
# Public process_message() function
# ---------------------------------------------------------------------------


async def process_message(
    message: str,
    conversation_context: list,
    active_filters: dict,
    business_name: str,
    client_ip: str = "unknown",
) -> dict:
    """Extract structured intent from a natural-language user message.

    This is the primary public interface for NL_Processor. It calls the
    configured LLM API, validates the response, applies injection detection
    and confidence thresholding, and returns a normalised result.

    Args:
        message:              The sanitised user message text.
        conversation_context: Ordered list of prior turns (``role``/``content``
                              dicts) for the current session.
        active_filters:       Currently-active filter constraints carried over
                              from prior turns in the session.
        business_name:        Display name of the business (used in system prompt).
        client_ip:            Caller's IP address for injection-incident logging.

    Returns:
        A dict with keys:
          - ``intent``          — extracted intent string
          - ``filters``         — newly parsed filter values (None-stripped)
          - ``active_filters``  — merged filters (new overrides old, Req 3.2)
          - ``confidence_score``— float 0.0–1.0
          - ``reply``           — natural-language reply for the user

    Error handling (Req 6.7):
        - ``httpx.HTTPStatusError`` (4xx / 5xx) → HTTP 200 with FALLBACK_RESPONSE
        - ``httpx.ConnectError`` / ``httpx.RemoteProtocolError`` → HTTP 200 with FALLBACK_RESPONSE
        - ``httpx.ReadTimeout`` → HTTP 200 with FALLBACK_RESPONSE (TCP drop / fatal)
        - Malformed / non-JSON LLM response → FALLBACK_RESPONSE
        - Prompt injection detected → log + FALLBACK_RESPONSE (Req 9.3)
        - Confidence < 0.6 → intent overridden to "clarify" (Req 2.2)
        - Out-of-scope intents → decline message + empty products hint (Req 9.6)
    """
    provider = _env("LLM_PROVIDER", "openai").lower()
    system_prompt = _build_system_prompt(business_name)
    timeout = _timeout()

    # Build the messages array: system prompt + conversation context + user turn
    messages: list[dict] = []

    if provider == "openai":
        # OpenAI accepts a "system" role at the start of the messages array
        messages.append({"role": "system", "content": system_prompt})

    # Append conversation context — only user turns are passed to the LLM.
    # Assistant turns are English prose which confuses models like Nova into
    # continuing in prose mode instead of outputting JSON.
    # We only give the model the user's prior questions for context continuity.
    for turn in conversation_context:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "system":
            continue
        if role == "assistant":
            # Summarise assistant turns as a brief system note rather than
            # injecting prose that could derail JSON output
            continue
        messages.append({"role": "user", "content": content})

    # Append the current user message (avoid duplicate if context already has it)
    if not messages or messages[-1].get("content") != message:
        messages.append({"role": "user", "content": message})

    # ------------------------------------------------------------------
    # LLM API call (Req 2.1 — NL_Processor calls LLM within 200ms of receipt)
    # ------------------------------------------------------------------
    raw_content: str = ""
    try:
        if provider == "bedrock":
            # Bedrock uses boto3 (synchronous) — run in a thread to avoid
            # blocking the asyncio event loop.
            import asyncio

            try:
                raw_content = await asyncio.to_thread(
                    _call_bedrock, system_prompt, messages
                )
            except Exception as exc:  # noqa: BLE001
                # Catch boto3 ClientError, EndpointResolutionError, etc.
                # and map to the same fallback path as httpx errors (Req 6.7).
                logger.error(
                    "Bedrock invocation error | model=%s ip=%s error=%s",
                    _env("LLM_MODEL"),
                    client_ip,
                    exc,
                )
                return _fallback_result(active_filters)
        else:
            async with httpx.AsyncClient(timeout=timeout) as client_http:
                if provider == "anthropic":
                    raw_content = await _call_anthropic(client_http, system_prompt, messages)
                else:
                    # Default to OpenAI for any unrecognised provider value
                    raw_content = await _call_openai(client_http, messages)

    except httpx.HTTPStatusError as exc:
        # 4xx / 5xx from LLM API — return HTTP 200 with FALLBACK_RESPONSE (Req 6.7)
        logger.error(
            "LLM HTTP error | provider=%s status=%d ip=%s",
            provider,
            exc.response.status_code,
            client_ip,
        )
        return _fallback_result(active_filters)

    except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
        # TCP drop or protocol-level failure (Req 6.7)
        logger.error(
            "LLM connection error | provider=%s error=%s ip=%s",
            provider,
            exc,
            client_ip,
        )
        return _fallback_result(active_filters)

    except httpx.ReadTimeout as exc:
        # HTTP client's timeout exceeded — the LLM took longer than
        # LLM_TIMEOUT_SECONDS; treat as a fatal connection drop (Req 6.7).
        # Note: per design, if the LLM is slow-but-alive we wait (httpx will
        # not time out mid-stream unless ReadTimeout fires).  When it fires,
        # we consider the connection dropped.
        logger.error(
            "LLM read timeout | provider=%s timeout=%.1fs ip=%s error=%s",
            provider,
            timeout,
            client_ip,
            exc,
        )
        return _fallback_result(active_filters)

    # ------------------------------------------------------------------
    # Parse the LLM response as JSON
    # Models like Amazon Nova sometimes wrap output in markdown fences or
    # append trailing characters. We strip those robustly before parsing.
    # ------------------------------------------------------------------
    cleaned_content = raw_content.strip()

    # Remove ```json ... ``` or ``` ... ``` wrappers
    if cleaned_content.startswith("```"):
        lines = cleaned_content.split("\n")
        inner_lines = []
        for line in lines[1:]:
            if line.strip() == "```":
                break
            inner_lines.append(line)
        cleaned_content = "\n".join(inner_lines).strip()

    # Extract the first complete JSON object using brace matching
    # This handles cases where the model appends trailing text like ]}
    if cleaned_content.startswith("{"):
        depth = 0
        end_idx = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(cleaned_content):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i + 1
                        break
        if end_idx > 0:
            cleaned_content = cleaned_content[:end_idx]

    try:
        parsed: dict = json.loads(cleaned_content)
    except (json.JSONDecodeError, ValueError):
        logger.error(
            "LLM returned non-JSON response | provider=%s ip=%s raw=%r",
            provider,
            client_ip,
            raw_content[:200],
        )
        return _fallback_result(active_filters)

    if not isinstance(parsed, dict):
        logger.error(
            "LLM JSON is not an object | provider=%s ip=%s type=%s",
            provider,
            client_ip,
            type(parsed).__name__,
        )
        return _fallback_result(active_filters)

    # ------------------------------------------------------------------
    # Prompt-injection detection (Req 9.3)
    # Check all string fields in the LLM response for injection patterns.
    # On match: log timestamp + IP, discard turn, return FALLBACK_RESPONSE.
    # ------------------------------------------------------------------
    if _check_injection(parsed, client_ip):
        return _fallback_result(active_filters)

    # ------------------------------------------------------------------
    # Normalise: apply confidence threshold + filter merge rule (Req 3.2)
    # ------------------------------------------------------------------
    result = _normalise(parsed, active_filters)

    # ------------------------------------------------------------------
    # Out-of-scope intent handling (Req 9.6)
    # Decline add_to_cart, place_order, change_password, and any other
    # explicitly out-of-scope intents with an empty products array.
    # The "out_of_scope" intent from the LLM is also declined here.
    # ------------------------------------------------------------------
    if result["intent"] in _OUT_OF_SCOPE_INTENTS or result["intent"] == "out_of_scope":
        result["intent"] = "out_of_scope"
        result["reply"] = _OUT_OF_SCOPE_REPLY
        # Caller is responsible for returning an empty products list
        # (no filter merge change needed — active_filters preserved)

    return result


# ---------------------------------------------------------------------------
# Backwards-compatible alias (used by older router code that calls parse())
# ---------------------------------------------------------------------------

async def parse(
    message: str,
    conversation_context: list,
    active_filters: dict,
    client_ip: str = "unknown",
    business_name: str = "",
) -> dict:
    """Backwards-compatible wrapper around ``process_message``.

    The argument order differs from ``process_message`` to maintain
    compatibility with any existing callers.  New code should call
    ``process_message`` directly.
    """
    return await process_message(
        message=message,
        conversation_context=conversation_context,
        active_filters=active_filters,
        business_name=business_name,
        client_ip=client_ip,
    )
