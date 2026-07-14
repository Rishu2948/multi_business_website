"""
ai-chatbot/tests/test_properties.py
Property-based tests for the AI Catalog Chatbot service.

Uses Hypothesis for property generation.

Profiles:
  - "ci": max_examples=100  (used in CI and local test runs)
"""

from __future__ import annotations

import uuid

from hypothesis import given, settings, strategies as st

# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------

settings.register_profile("ci", max_examples=100)
settings.load_profile("ci")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Import module-level state so we can reset between examples
from middleware import rate_limiter as rl


def _reset_state() -> None:
    """Clear in-process IP tracking dict to avoid cross-example pollution."""
    with rl._lock:
        rl._ip_timestamps.clear()


# ---------------------------------------------------------------------------
# Property 14: Rate limiter enforces 30-request cap per 60-second sliding window
# Feature: ai-catalog-chatbot, Property 14
# Validates: Requirements 9.4
# ---------------------------------------------------------------------------

@settings(max_examples=100)
@given(n=st.integers(min_value=1, max_value=50))
def test_rate_limiter_enforces_30_request_cap(n: int) -> None:
    """
    **Validates: Requirements 9.4**

    Property 14: Rate limiter enforces 30-request cap per 60-second sliding window.

    For any sequence of N requests (1–50) from the same IP address:
    - The first 30 requests must be allowed (check_rate_limit returns True).
    - Every request from the 31st onward must be blocked (check_rate_limit returns False).

    A fresh UUID is used as the IP for each example to avoid state contamination
    between Hypothesis examples.

    # Feature: ai-catalog-chatbot, Property 14
    """
    # Use a unique IP per example to avoid inter-test contamination
    ip = str(uuid.uuid4())

    results = [rl.check_rate_limit(ip) for _ in range(n)]

    cap = rl._MAX_REQUESTS  # 30

    for i, allowed in enumerate(results):
        request_number = i + 1  # 1-indexed for readability
        if request_number <= cap:
            assert allowed is True, (
                f"Request #{request_number} from IP {ip!r} should be ALLOWED "
                f"(within the {cap}-request cap) but check_rate_limit returned False."
            )
        else:
            assert allowed is False, (
                f"Request #{request_number} from IP {ip!r} should be BLOCKED "
                f"(exceeds the {cap}-request cap) but check_rate_limit returned True."
            )
