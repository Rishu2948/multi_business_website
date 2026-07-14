"""
Smoke tests for the pure-Python UDF logic in 02_bronze_to_silver.py.
No PySpark required — tests the functions directly.
"""
import re
import hashlib
from typing import Optional

# ---------------------------------------------------------------------------
# Inline the UDF implementations (duplicated from the notebook for testability)
# ---------------------------------------------------------------------------

_RE_IPV4 = re.compile(r'\b\d{1,3}(\.\d{1,3}){3}\b')
_RE_ACCOUNT = re.compile(r'\b\d{12}\b')
_RE_BEARER = re.compile(r'Bearer\s+\S+', re.IGNORECASE)
_RE_CREDENTIAL = re.compile(r'(password|token|secret|api[_-]?key)[=:]\S+', re.IGNORECASE)


def redact_pii(text):
    if text is None:
        return None
    text = _RE_IPV4.sub('[IP]', text)
    text = _RE_ACCOUNT.sub('[ACCOUNT]', text)
    text = _RE_BEARER.sub('Bearer [REDACTED]', text)
    text = _RE_CREDENTIAL.sub('[REDACTED]', text)
    return text


_RE_LEVEL = re.compile(
    r'\b(DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRITICAL|FATAL|SEVERE)\b', re.IGNORECASE
)


def extract_level(raw):
    if not raw:
        return None
    m = _RE_LEVEL.search(raw)
    if not m:
        return None
    level = m.group(1).upper()
    return "WARN" if level == "WARNING" else level


_ERROR_CATEGORY_RULES = [
    ("timeout",            re.compile(r'timeout|timed\s+out',                re.IGNORECASE)),
    ("connection_refused", re.compile(r'connection\s+refused|connection\s+reset', re.IGNORECASE)),
    ("out_of_memory",      re.compile(r'out\s+of\s+memory|\boom\b',          re.IGNORECASE)),
    ("null_pointer",       re.compile(r'\bnull|\bnpe\b',                     re.IGNORECASE)),
    ("auth_failure",       re.compile(r'\b401\b|\b403\b|unauthorized',       re.IGNORECASE)),
    ("circuit_breaker",    re.compile(r'circuit',                             re.IGNORECASE)),
    ("internal_error",     re.compile(r'\b500\b',                             re.IGNORECASE)),
]


def categorize_error(raw):
    if not raw:
        return "other"
    for category, pattern in _ERROR_CATEGORY_RULES:
        if pattern.search(raw):
            return category
    return "other"


def compute_log_id(service, time_val, raw):
    svc = service if service is not None else ""
    t   = str(time_val) if time_val is not None else ""
    r   = raw if raw is not None else ""
    return hashlib.sha256((svc + t + r).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_redact_pii_ipv4():
    assert redact_pii("connect from 192.168.1.100 failed") == "connect from [IP] failed"
    assert redact_pii("10.0.0.1 and 172.16.254.1") == "[IP] and [IP]"


def test_redact_pii_account():
    assert redact_pii("account 123456789012 blocked") == "account [ACCOUNT] blocked"


def test_redact_pii_bearer():
    assert redact_pii("auth: Bearer eyJhbGciOiJSUzI1NiJ9") == "auth: Bearer [REDACTED]"
    assert redact_pii("BEARER abc123") == "Bearer [REDACTED]"


def test_redact_pii_credentials():
    assert redact_pii("password=s3cr3t123") == "[REDACTED]"
    assert redact_pii("api_key:abc123def") == "[REDACTED]"
    assert redact_pii("api-key=xyz789") == "[REDACTED]"
    assert redact_pii("token=abc secret=def") == "[REDACTED] [REDACTED]"


def test_redact_pii_none():
    assert redact_pii(None) is None


def test_extract_level():
    assert extract_level("2024-01-01 ERROR NullPointerException") == "ERROR"
    assert extract_level("WARNING: disk full") == "WARN"
    assert extract_level("INFO startup complete") == "INFO"
    assert extract_level("no level here") is None
    assert extract_level(None) is None


def test_categorize_error_priority():
    # timeout wins over connection_refused
    assert categorize_error("connection refused after timeout") == "timeout"
    assert categorize_error("request timed out") == "timeout"


def test_categorize_error_connection():
    assert categorize_error("connection refused to host") == "connection_refused"
    assert categorize_error("connection reset by peer") == "connection_refused"


def test_categorize_error_oom():
    assert categorize_error("out of memory error") == "out_of_memory"
    assert categorize_error("java.lang.OutOfMemoryError: OOM") == "out_of_memory"


def test_categorize_error_null():
    assert categorize_error("NullPointerException at line 42") == "null_pointer"
    assert categorize_error("value is null") == "null_pointer"


def test_categorize_error_auth():
    assert categorize_error("HTTP 401 unauthorized") == "auth_failure"
    assert categorize_error("HTTP 403 forbidden") == "auth_failure"


def test_categorize_error_circuit():
    assert categorize_error("circuit breaker open") == "circuit_breaker"


def test_categorize_error_internal():
    assert categorize_error("status 500 internal server error") == "internal_error"


def test_categorize_error_other():
    assert categorize_error("some other problem") == "other"
    assert categorize_error(None) == "other"
    assert categorize_error("") == "other"


def test_compute_log_id_deterministic():
    id1 = compute_log_id("checkout", 1700000000000, "ERROR timeout")
    id2 = compute_log_id("checkout", 1700000000000, "ERROR timeout")
    assert id1 == id2


def test_compute_log_id_unique():
    id1 = compute_log_id("checkout", 1700000000000, "ERROR timeout")
    id3 = compute_log_id("payment", 1700000000000, "ERROR timeout")
    assert id1 != id3


def test_compute_log_id_null_service():
    id4 = compute_log_id(None, 1700000000000, "ERROR")
    assert isinstance(id4, str) and len(id4) == 64
