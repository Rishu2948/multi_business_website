# Databricks notebook source
# Community Edition compatible — two-part table names (no Unity Catalog)
# Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 8.3

# COMMAND ----------
# MAGIC %md
# MAGIC # SRE Copilot — Bronze → Silver Transformation (`02_bronze_to_silver.py`)
# MAGIC
# MAGIC **Purpose:** Read unprocessed records from `bronze.app_logs`, apply PII redaction,
# MAGIC extract structured fields via regex UDFs, categorise errors, compute a deduplication
# MAGIC hash, filter out null-service records, and write cleaned rows to `silver.logs`.
# MAGIC Writes a checkpoint entry to `config.pipeline_checkpoints` on every run.
# MAGIC
# MAGIC **Schedule:** Run after `00_cw_export.py` via Databricks Community Edition UI Scheduler.
# MAGIC
# MAGIC **Tables read:**   `bronze.app_logs`
# MAGIC **Tables written:** `silver.logs`, `config.pipeline_checkpoints`
# MAGIC
# MAGIC **Requirements:** 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 8.3

# COMMAND ----------
# MAGIC %md ## 1. Imports and Spark session

# COMMAND ----------

import re
import time
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, StructType, StructField, LongType

spark = SparkSession.getActiveSession()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("02_bronze_to_silver")

# COMMAND ----------
# MAGIC %md ## 2. PII Redactor UDF
# MAGIC
# MAGIC Redacts the following patterns from any text string (Requirement 2.2):
# MAGIC
# MAGIC | Pattern | Replacement |
# MAGIC |---|---|
# MAGIC | IPv4 addresses `\b\d{1,3}(\.\d{1,3}){3}\b` | `[IP]` |
# MAGIC | 12-digit sequences `\b\d{12}\b` | `[ACCOUNT]` |
# MAGIC | Bearer tokens `Bearer\s+\S+` | `Bearer [REDACTED]` |
# MAGIC | Credential key-value pairs `(password\|token\|secret\|api[_-]?key)[=:]\S+` | `[REDACTED]` |

# COMMAND ----------

# Pre-compiled patterns for efficiency (compiled once at UDF definition time,
# reused across all rows in the same executor task).
_RE_IPV4 = re.compile(r'\b\d{1,3}(\.\d{1,3}){3}\b')
_RE_ACCOUNT = re.compile(r'\b\d{12}\b')
_RE_BEARER = re.compile(r'Bearer\s+\S+', re.IGNORECASE)
_RE_CREDENTIAL = re.compile(
    r'(password|token|secret|api[_-]?key)[=:]\S+',
    re.IGNORECASE,
)


def redact_pii(text: Optional[str]) -> Optional[str]:
    """
    Replace PII patterns in *text* and return the redacted string.

    Redaction order:
    1. IPv4 addresses          → [IP]
    2. 12-digit account numbers → [ACCOUNT]
    3. Bearer tokens           → Bearer [REDACTED]
    4. Credential key-value    → [REDACTED]  (replaces the entire key=value pair)

    Returns None when *text* is None.

    Requirements: 2.2
    """
    if text is None:
        return None
    # 1. IPv4 — replace before account numbers to avoid partial digit overlap
    text = _RE_IPV4.sub('[IP]', text)
    # 2. 12-digit account numbers
    text = _RE_ACCOUNT.sub('[ACCOUNT]', text)
    # 3. Bearer tokens (case-insensitive; replaces "Bearer <token>")
    text = _RE_BEARER.sub('Bearer [REDACTED]', text)
    # 4. Credential key=value / key:value pairs (case-insensitive)
    text = _RE_CREDENTIAL.sub('[REDACTED]', text)
    return text


# Register as a Spark SQL UDF so it can be used in both DataFrame API and SQL cells.
redact_pii_udf = spark.udf.register("redact_pii", redact_pii, StringType())

# COMMAND ----------
# MAGIC %md ## 3. Field-Extraction UDFs
# MAGIC
# MAGIC Each UDF applies regex patterns to the raw log string and returns the
# MAGIC first match (or `null` when the pattern is absent — Requirement 2.1).

# COMMAND ----------

# ---------------------------------------------------------------------------
# 3a. service extraction
# ---------------------------------------------------------------------------
# Matches patterns commonly emitted by structured loggers, e.g.:
#   service=checkout-service
#   "service":"checkout-service"
#   service: checkout-service
# ---------------------------------------------------------------------------
_RE_SERVICE = re.compile(
    r'(?:service[=:\s"\']+)([a-zA-Z0-9][\w\-\.]{0,63})',
    re.IGNORECASE,
)


def extract_service(raw: Optional[str]) -> Optional[str]:
    """
    Extract the service name from a raw log string.

    Returns the first captured group, or None if no match.
    Requirements: 2.1
    """
    if not raw:
        return None
    m = _RE_SERVICE.search(raw)
    return m.group(1) if m else None


extract_service_udf = spark.udf.register("extract_service", extract_service, StringType())

# ---------------------------------------------------------------------------
# 3b. region extraction
# ---------------------------------------------------------------------------
# Matches AWS region codes, e.g.:
#   region=us-west-2
#   "region":"eu-central-1"
# ---------------------------------------------------------------------------
_RE_REGION = re.compile(
    r'(?:region[=:\s"\']+)((?:us|eu|ap|sa|ca|me|af|cn)-(?:east|west|north|south|'
    r'central|northeast|southeast|northwest|southwest)-\d)',
    re.IGNORECASE,
)


def extract_region(raw: Optional[str]) -> Optional[str]:
    """
    Extract an AWS region identifier from a raw log string.

    Returns the region string (e.g. "us-west-2"), or None if absent.
    Requirements: 2.1
    """
    if not raw:
        return None
    m = _RE_REGION.search(raw)
    return m.group(1).lower() if m else None


extract_region_udf = spark.udf.register("extract_region", extract_region, StringType())

# ---------------------------------------------------------------------------
# 3c. log-level extraction
# ---------------------------------------------------------------------------
# Matches the standard syslog / application log levels anywhere in the message,
# including bracket-quoted forms like [ERROR], "level":"WARN", etc.
# ---------------------------------------------------------------------------
_RE_LEVEL = re.compile(
    r'\b(DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|CRITICAL|FATAL|SEVERE)\b',
    re.IGNORECASE,
)


def extract_level(raw: Optional[str]) -> Optional[str]:
    """
    Extract the log level from a raw log string.

    Normalises WARN/WARNING → WARN, returns upper-case.
    Returns None when no level keyword is detected.
    Requirements: 2.1
    """
    if not raw:
        return None
    m = _RE_LEVEL.search(raw)
    if not m:
        return None
    level = m.group(1).upper()
    return "WARN" if level == "WARNING" else level


extract_level_udf = spark.udf.register("extract_level", extract_level, StringType())

# ---------------------------------------------------------------------------
# 3d. error-type extraction
# ---------------------------------------------------------------------------
# Captures Java / Python / JavaScript-style exception class names, e.g.:
#   java.net.ConnectionRefusedException
#   NullPointerException
#   TimeoutError
# Also captures common short-form tokens like "TimeoutError", "OOMError".
# ---------------------------------------------------------------------------
_RE_ERROR_TYPE = re.compile(
    r'(?:(?:[a-zA-Z_][\w\.]*\.)?'         # optional package prefix
    r'([A-Z][a-zA-Z0-9]*(?:Exception|Error|Failure|Fault|Timeout|Panic)))',
)


def extract_error_type(raw: Optional[str]) -> Optional[str]:
    """
    Extract the exception / error class name from a raw log string.

    Returns the first match, or None when no exception class is found.
    Requirements: 2.1
    """
    if not raw:
        return None
    m = _RE_ERROR_TYPE.search(raw)
    return m.group(1) if m else None


extract_error_type_udf = spark.udf.register(
    "extract_error_type", extract_error_type, StringType()
)

# ---------------------------------------------------------------------------
# 3e. trace-ID extraction
# ---------------------------------------------------------------------------
# Matches common distributed-tracing trace-ID formats:
#   trace_id=abc123...
#   traceId: "abc123..."
#   X-Trace-Id: abc123...
#   x-b3-traceid: abc123... (Zipkin B3)
# ---------------------------------------------------------------------------
_RE_TRACE_ID = re.compile(
    r'(?:trace[-_]?id|x-b3-traceid|traceid)[=:\s"\']+([0-9a-fA-F\-]{8,64})',
    re.IGNORECASE,
)


def extract_trace_id(raw: Optional[str]) -> Optional[str]:
    """
    Extract a distributed-tracing trace ID from a raw log string.

    Returns the trace-ID string, or None when absent.
    Requirements: 2.1
    """
    if not raw:
        return None
    m = _RE_TRACE_ID.search(raw)
    return m.group(1) if m else None


extract_trace_id_udf = spark.udf.register(
    "extract_trace_id", extract_trace_id, StringType()
)

# COMMAND ----------
# MAGIC %md ## 4. Error Categorisation UDF
# MAGIC
# MAGIC Assigns one of eight error categories using **first-match** priority
# MAGIC (Requirement 2.3):
# MAGIC
# MAGIC | Priority | Category | Keywords (case-insensitive) |
# MAGIC |---|---|---|
# MAGIC | 1 | `timeout` | "timeout", "timed out" |
# MAGIC | 2 | `connection_refused` | "connection refused", "connection reset" |
# MAGIC | 3 | `out_of_memory` | "out of memory", "oom" |
# MAGIC | 4 | `null_pointer` | "null", "npe" |
# MAGIC | 5 | `auth_failure` | "401", "403", "unauthorized" |
# MAGIC | 6 | `circuit_breaker` | "circuit" |
# MAGIC | 7 | `internal_error` | "500" |
# MAGIC | 8 | `other` | (default) |

# COMMAND ----------

# Priority-ordered list of (category, compiled_pattern) tuples.
# The list is evaluated in order; the first match determines the category.
_ERROR_CATEGORY_RULES = [
    ("timeout",            re.compile(r'timeout|timed\s+out',             re.IGNORECASE)),
    ("connection_refused", re.compile(r'connection\s+refused|connection\s+reset', re.IGNORECASE)),
    ("out_of_memory",      re.compile(r'out\s+of\s+memory|\boom\b',       re.IGNORECASE)),
    ("null_pointer",       re.compile(r'\bnull|\bnpe\b',                  re.IGNORECASE)),
    ("auth_failure",       re.compile(r'\b401\b|\b403\b|unauthorized',    re.IGNORECASE)),
    ("circuit_breaker",    re.compile(r'circuit',                          re.IGNORECASE)),
    ("internal_error",     re.compile(r'\b500\b',                          re.IGNORECASE)),
]


def categorize_error(raw: Optional[str]) -> str:
    """
    Return the error category for a raw log string using first-match priority.

    Always returns a non-null string from the closed set:
      timeout | connection_refused | out_of_memory | null_pointer |
      auth_failure | circuit_breaker | internal_error | other

    Requirements: 2.3
    """
    if not raw:
        return "other"
    for category, pattern in _ERROR_CATEGORY_RULES:
        if pattern.search(raw):
            return category
    return "other"


categorize_error_udf = spark.udf.register(
    "categorize_error", categorize_error, StringType()
)

# COMMAND ----------
# MAGIC %md ## 5. log_id computation helper
# MAGIC
# MAGIC `log_id = SHA-256(service || str(_time) || _raw)` (Requirement 2.4).
# MAGIC The UDF is registered but we compute it via a Python UDF column expression
# MAGIC for efficiency.

# COMMAND ----------


def compute_log_id(service: Optional[str], time_val: Optional[int],
                   raw: Optional[str]) -> str:
    """
    Compute a deterministic SHA-256 log_id.

    Concatenates service (empty string when null), _time as str, and _raw,
    then returns the hex digest.

    Requirements: 2.4
    """
    svc = service if service is not None else ""
    t   = str(time_val) if time_val is not None else ""
    r   = raw if raw is not None else ""
    return hashlib.sha256((svc + t + r).encode("utf-8")).hexdigest()


compute_log_id_udf = F.udf(compute_log_id, StringType())

# COMMAND ----------
# MAGIC %md ## 6. Checkpoint writer

# COMMAND ----------


def _write_checkpoint(batch_id: str,
                      start_time: datetime,
                      record_count: Optional[int],
                      status: str,
                      error_message: Optional[str] = None) -> None:
    """
    Append a single row to ``config.pipeline_checkpoints``.

    Failures here are logged to stdout but never re-raised (Requirement 8.3 / 8.5).
    """
    end_time = datetime.now(timezone.utc)
    try:
        df = (
            spark.createDataFrame(
                [(
                    batch_id,
                    "02_bronze_to_silver",
                    record_count,
                    start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    status,
                    error_message,
                )],
                schema=["batch_id", "notebook", "record_count",
                        "start_time", "end_time", "status", "error_message"],
            )
            .withColumn("start_time", F.to_timestamp("start_time"))
            .withColumn("end_time",   F.to_timestamp("end_time"))
            .withColumn("record_count", F.col("record_count").cast("long"))
        )
        df.write.format("delta").mode("append").saveAsTable(
            "config.pipeline_checkpoints"
        )
        logger.info("Checkpoint written: batch_id=%s status=%s", batch_id, status)
    except Exception as cp_err:
        print(f"[02_bronze_to_silver] WARNING: checkpoint write failed — {cp_err}")

# COMMAND ----------
# MAGIC %md ## 7. Main transformation pipeline

# COMMAND ----------

_run_start   = datetime.now(timezone.utc)
_batch_id    = _run_start.strftime("silver-%Y%m%d-%H%M%S")
_status      = "failed"
_record_count: Optional[int] = None
_error_msg:   Optional[str]  = None

try:
    # ------------------------------------------------------------------ #
    # 7a. Read from Bronze                                                 #
    # ------------------------------------------------------------------ #
    logger.info("Reading bronze.app_logs …")
    df_bronze = spark.table("bronze.app_logs")

    # ------------------------------------------------------------------ #
    # 7b. Apply PII redaction to _raw (Requirement 2.2)                   #
    # ------------------------------------------------------------------ #
    df = df_bronze.withColumn("message", redact_pii_udf(F.col("_raw")))

    # ------------------------------------------------------------------ #
    # 7c. Extract structured fields from _raw (Requirement 2.1)           #
    # ------------------------------------------------------------------ #
    df = (
        df
        .withColumn("service",    extract_service_udf(F.col("_raw")))
        .withColumn("region",     extract_region_udf(F.col("_raw")))
        .withColumn("level",      extract_level_udf(F.col("_raw")))
        .withColumn("error_type", extract_error_type_udf(F.col("_raw")))
        .withColumn("trace_id",   extract_trace_id_udf(F.col("_raw")))
    )

    # ------------------------------------------------------------------ #
    # 7d. Default region to "us-west-2" when not extracted                #
    # ------------------------------------------------------------------ #
    df = df.withColumn(
        "region",
        F.when(F.col("region").isNull(), F.lit("us-west-2")).otherwise(F.col("region")),
    )

    # ------------------------------------------------------------------ #
    # 7e. Error categorisation (Requirement 2.3)                          #
    # ------------------------------------------------------------------ #
    df = df.withColumn("error_category", categorize_error_udf(F.col("_raw")))

    # ------------------------------------------------------------------ #
    # 7f. Compute log_id = SHA-256(service || str(_time) || _raw)         #
    #     (Requirements 2.4)                                              #
    # ------------------------------------------------------------------ #
    df = df.withColumn(
        "log_id",
        compute_log_id_udf(F.col("service"), F.col("_time"), F.col("_raw")),
    )

    # ------------------------------------------------------------------ #
    # 7g. Anonymise host → host_alias (design: "host-" + abs(hash) % 100) #
    # ------------------------------------------------------------------ #
    df = df.withColumn(
        "host_alias",
        F.concat(
            F.lit("host-"),
            (F.abs(F.hash(F.col("host"))) % 100).cast("string"),
        ),
    )

    # ------------------------------------------------------------------ #
    # 7h. Convert _time (epoch ms) → timestamp column                     #
    # ------------------------------------------------------------------ #
    df = df.withColumn(
        "timestamp",
        F.to_timestamp((F.col("_time") / 1000).cast("long")),
    )

    # ------------------------------------------------------------------ #
    # 7i. Discard records where service is null (Requirement 2.6)         #
    # ------------------------------------------------------------------ #
    df_filtered = df.filter(F.col("service").isNotNull())

    # ------------------------------------------------------------------ #
    # 7j. Deduplicate on log_id (Requirement 2.5)                         #
    # ------------------------------------------------------------------ #
    df_deduped = df_filtered.dropDuplicates(["log_id"])

    # ------------------------------------------------------------------ #
    # 7k. Select final Silver schema                                       #
    # ------------------------------------------------------------------ #
    _processed_at_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    df_silver = (
        df_deduped
        .select(
            F.col("log_id"),
            F.col("timestamp"),
            F.col("service"),
            F.col("region"),
            F.col("level"),
            F.col("message"),
            F.col("error_type"),
            F.col("error_category"),
            F.col("trace_id"),
            F.col("host_alias"),
            F.to_timestamp(F.lit(_processed_at_ts)).alias("_processed_at"),
        )
    )

    # ------------------------------------------------------------------ #
    # 7l. Write to silver.logs partitioned by region, service             #
    #     (Requirement 2.7)                                               #
    # ------------------------------------------------------------------ #
    logger.info("Writing to silver.logs …")
    (
        df_silver
        .write
        .format("delta")
        .mode("append")
        .partitionBy("region", "service")
        .option("mergeSchema", "true")
        .saveAsTable("silver.logs")
    )

    _record_count = df_silver.count()
    _status = "success"
    logger.info(
        "02_bronze_to_silver complete: batch_id=%s records=%d",
        _batch_id, _record_count,
    )

except Exception as exc:
    _error_msg = str(exc)
    logger.error(
        "02_bronze_to_silver failed: %s", _error_msg, exc_info=True
    )

# COMMAND ----------
# MAGIC %md ## 8. Write checkpoint (always)

# COMMAND ----------

# Write checkpoint regardless of success or failure (Requirement 8.3).
_write_checkpoint(
    batch_id=_batch_id,
    start_time=_run_start,
    record_count=_record_count,
    status=_status,
    error_message=_error_msg,
)

# COMMAND ----------
# MAGIC %md ## 9. Run summary

# COMMAND ----------

print("=" * 60)
print("02_bronze_to_silver run complete")
print(f"  batch_id   : {_batch_id}")
print(f"  status     : {_status}")
print(f"  records    : {_record_count if _record_count is not None else 'N/A (failed)'}")
if _error_msg:
    print(f"  error      : {_error_msg}")
print("=" * 60)

# Surface the failure so the Databricks UI marks the job as failed.
if _status == "failed":
    raise RuntimeError(
        f"[02_bronze_to_silver] Transformation failed (batch_id={_batch_id!r}): {_error_msg}"
    )
