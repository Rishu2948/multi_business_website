# Databricks notebook source
# Community Edition compatible — two-part table names (no Unity Catalog)
# Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 8.3

# COMMAND ----------
# MAGIC %md
# MAGIC # SRE Copilot — CloudWatch Export → Bronze Layer (`00_cw_export.py`)
# MAGIC
# MAGIC **Purpose:** Pull a rolling 2-hour window of CloudWatch log events and append them
# MAGIC to the `bronze.app_logs` Delta table, deduplicating on the composite key
# MAGIC `(log_group, log_stream, _time, _raw)`. Writes a checkpoint entry to
# MAGIC `config.pipeline_checkpoints` on every run regardless of success or failure.
# MAGIC
# MAGIC **Schedule:** Run every hour via Databricks Community Edition UI Scheduler.
# MAGIC
# MAGIC **Tables written:**
# MAGIC - `bronze.app_logs` — appended (on success only)
# MAGIC - `config.pipeline_checkpoints` — always written
# MAGIC
# MAGIC **Requirements:** 1.1, 1.2, 1.3, 1.5, 1.6, 8.3

# COMMAND ----------
# MAGIC %md ## 1. Widgets / Configuration

# COMMAND ----------

# Widget: CloudWatch log group to export.
# Set via notebook widget or override with an environment variable when called
# programmatically from the backfill notebook (01_backfill.py).
dbutils.widgets.text("LOG_GROUP_NAME", "/aws/lambda/checkout-service",
                     "CloudWatch Log Group Name")
dbutils.widgets.text("AWS_REGION", "us-east-1", "AWS Region")

# COMMAND ----------
# MAGIC %md ## 2. Imports and helpers

# COMMAND ----------

import json
import time
import boto3
import logging
from datetime import datetime, timezone
from typing import Optional

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType
)

# Use the Spark session provided by Databricks
spark = SparkSession.getActiveSession()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("00_cw_export")

# COMMAND ----------
# MAGIC %md ## 3. Secret retrieval

# COMMAND ----------


def _get_cloudwatch_credentials(secret_name: str = "sre/cloudwatch-credentials",
                                region: str = "us-east-1") -> dict:
    """
    Retrieve CloudWatch credentials from AWS Secrets Manager.

    Returns a dict with keys:
      - aws_access_key_id
      - aws_secret_access_key
      - (optionally) aws_session_token

    The secret value must be stored as a JSON string in Secrets Manager.
    """
    sm_client = boto3.client("secretsmanager", region_name=region)
    response = sm_client.get_secret_value(SecretId=secret_name)
    secret_str = response["SecretString"]
    return json.loads(secret_str)


# COMMAND ----------
# MAGIC %md ## 4. Source and host derivation helpers

# COMMAND ----------


def _derive_source(log_group: str) -> str:
    """
    Derive a clean ``source`` string from a CloudWatch log group name.

    Examples:
      /aws/lambda/checkout-service  → checkout-service
      /aws/ecs/payment-service      → payment-service
      /my-app/frontend              → frontend
      plain-name                    → plain-name
    """
    if not log_group:
        return log_group
    # Strip common AWS prefixes so the source is just the service name.
    for prefix in ("/aws/lambda/", "/aws/ecs/", "/aws/eks/",
                   "/aws/rds/", "/aws/"):
        if log_group.startswith(prefix):
            return log_group[len(prefix):]
    # For paths like /my-company/my-service, return the last path component.
    return log_group.rstrip("/").rsplit("/", 1)[-1]


def _derive_host(log_stream: str) -> str:
    """
    Derive a ``host`` value from a CloudWatch log stream name.

    For Lambda streams the format is typically:
      YYYY/MM/DD/[$LATEST|version]<hash>
    For ECS / container workloads it is often just a container ID or a
    descriptive name.  We return the stream name verbatim so that the original
    identifier is preserved and the Silver layer can anonymise it later.
    """
    return log_stream if log_stream else log_stream


# COMMAND ----------
# MAGIC %md ## 5. Checkpoint writer

# COMMAND ----------


def _write_checkpoint(batch_id: str,
                      start_time: datetime,
                      record_count: Optional[int],
                      status: str,
                      error_message: Optional[str] = None) -> None:
    """
    Append a single row to ``config.pipeline_checkpoints``.

    Called after every run regardless of success or failure (Requirement 8.3).
    Failures here are logged to stdout but never re-raised so they cannot mask
    the original pipeline result (Requirement 8.5).
    """
    end_time = datetime.now(timezone.utc)
    try:
        row = [(
            batch_id,
            "00_cw_export",
            record_count,
            start_time,
            end_time,
            status,
            error_message,
        )]
        schema = StructType([
            StructField("batch_id",      StringType(),  False),
            StructField("notebook",      StringType(),  False),
            StructField("record_count",  LongType(),    True),
            StructField("start_time",    StringType(),  False),  # will cast below
            StructField("end_time",      StringType(),  True),
            StructField("status",        StringType(),  False),
            StructField("error_message", StringType(),  True),
        ])
        # Build as strings first, then cast to TIMESTAMP for portability on
        # Databricks Community Edition (avoids Python datetime→Arrow edge cases).
        df = (
            spark.createDataFrame(
                [(
                    batch_id,
                    "00_cw_export",
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
        # Log only — never raise (Requirement 8.5).
        print(f"[00_cw_export] WARNING: checkpoint write failed — {cp_err}")


# COMMAND ----------
# MAGIC %md ## 6. Core export function

# COMMAND ----------


def export_bronze_window(log_group: str,
                         start_ms: int,
                         end_ms: int,
                         aws_region: str = "us-east-1",
                         secret_name: str = "sre/cloudwatch-credentials") -> int:
    """
    Export CloudWatch log events within [start_ms, end_ms) to ``bronze.app_logs``.

    This function is the primary entry-point used by both the scheduled hourly
    run (cell 7 below) **and** the backfill notebook (``01_backfill.py``), which
    imports this module and calls ``export_bronze_window`` directly.

    Parameters
    ----------
    log_group : str
        CloudWatch Logs log group name (e.g. ``/aws/lambda/checkout-service``).
    start_ms : int
        Start of the export window in Unix epoch milliseconds (inclusive).
    end_ms : int
        End of the export window in Unix epoch milliseconds (exclusive).
    aws_region : str
        AWS region where the log group lives.
    secret_name : str
        Secrets Manager secret ID that holds CloudWatch credentials.

    Returns
    -------
    int
        Number of records written to ``bronze.app_logs`` after deduplication.
        Returns 0 when the window is empty (no events found).

    Side effects
    ------------
    - Appends rows to ``bronze.app_logs`` (only on success with ≥1 event).
    - Does NOT write a checkpoint; the caller is responsible for checkpointing.

    Raises
    ------
    Exception
        Re-raises any CloudWatch API error so the caller can write a
        ``status='failed'`` checkpoint and stop processing (Requirement 1.3).
    """
    ingested_at = int(time.time() * 1000)
    batch_id = datetime.fromtimestamp(start_ms / 1000,
                                      tz=timezone.utc).strftime("hourly-%Y%m%d-%H%M")

    # ------------------------------------------------------------------ #
    # 6a. Retrieve credentials from Secrets Manager                       #
    # ------------------------------------------------------------------ #
    creds = _get_cloudwatch_credentials(
        secret_name=secret_name, region=aws_region
    )
    cw_client = boto3.client(
        "logs",
        region_name=aws_region,
        aws_access_key_id=creds.get("aws_access_key_id"),
        aws_secret_access_key=creds.get("aws_secret_access_key"),
        aws_session_token=creds.get("aws_session_token"),  # None if not present
    )

    # ------------------------------------------------------------------ #
    # 6b. Paginate through filter_log_events                              #
    # ------------------------------------------------------------------ #
    events = []
    kwargs = {
        "logGroupName": log_group,
        "startTime":    start_ms,
        "endTime":      end_ms,
        "limit":        10_000,   # max allowed by CloudWatch API
    }
    # boto3 paginators for filter_log_events are available in newer boto3
    # versions, but we loop manually for full compatibility with Community
    # Edition cluster library versions.
    while True:
        response = cw_client.filter_log_events(**kwargs)
        events.extend(response.get("events", []))
        next_token = response.get("nextToken")
        if not next_token:
            break
        kwargs["nextToken"] = next_token

    if not events:
        logger.info(
            "export_bronze_window: no events found for %s [%d, %d)",
            log_group, start_ms, end_ms,
        )
        return 0

    # ------------------------------------------------------------------ #
    # 6c. Map to Bronze schema (Requirement 1.1)                         #
    # ------------------------------------------------------------------ #
    source = _derive_source(log_group)
    rows = []
    for evt in events:
        log_stream = evt.get("logStreamName", "")
        host = _derive_host(log_stream)
        rows.append((
            evt.get("message", ""),   # _raw
            int(evt["timestamp"]),     # _time  (epoch ms, as emitted by CW)
            log_group,                 # log_group
            log_stream,                # log_stream
            source,                    # source
            host,                      # host
            ingested_at,               # _ingested_at
            batch_id,                  # _batch_id
        ))

    bronze_schema = StructType([
        StructField("_raw",          StringType(),  False),
        StructField("_time",         LongType(),    False),
        StructField("log_group",     StringType(),  False),
        StructField("log_stream",    StringType(),  False),
        StructField("source",        StringType(),  True),
        StructField("host",          StringType(),  True),
        StructField("_ingested_at",  LongType(),    False),
        StructField("_batch_id",     StringType(),  False),
    ])
    df_raw = spark.createDataFrame(rows, schema=bronze_schema)

    # ------------------------------------------------------------------ #
    # 6d. Deduplicate on composite key (Requirement 1.2)                 #
    # ------------------------------------------------------------------ #
    df_deduped = df_raw.dropDuplicates(
        ["log_group", "log_stream", "_time", "_raw"]
    )

    # ------------------------------------------------------------------ #
    # 6e. Append to bronze.app_logs (Delta, partition by date)           #
    # ------------------------------------------------------------------ #
    record_count = df_deduped.count()
    (
        df_deduped
        .write
        .format("delta")
        .mode("append")
        .saveAsTable("bronze.app_logs")
    )
    logger.info(
        "export_bronze_window: wrote %d records to bronze.app_logs "
        "(batch_id=%s, log_group=%s)",
        record_count, batch_id, log_group,
    )
    return record_count


# COMMAND ----------
# MAGIC %md ## 7. Scheduled hourly run — 2-hour rolling window

# COMMAND ----------

# Read widget values
_log_group  = dbutils.widgets.get("LOG_GROUP_NAME").strip()
_aws_region = dbutils.widgets.get("AWS_REGION").strip()

# Compute the 2-hour rolling window in epoch milliseconds (Requirement 1.2).
_now_ms   = int(time.time() * 1000)
_two_h_ms = 2 * 60 * 60 * 1000           # 2 hours in ms
_start_ms = _now_ms - _two_h_ms
_end_ms   = _now_ms

_batch_id   = datetime.fromtimestamp(_start_ms / 1000,
                                     tz=timezone.utc).strftime("hourly-%Y%m%d-%H%M")
_start_time = datetime.fromtimestamp(_start_ms / 1000, tz=timezone.utc)

logger.info(
    "Starting hourly CW export: log_group=%s window=[%s, %s] batch_id=%s",
    _log_group,
    datetime.fromtimestamp(_start_ms / 1000, tz=timezone.utc).isoformat(),
    datetime.fromtimestamp(_end_ms   / 1000, tz=timezone.utc).isoformat(),
    _batch_id,
)

# COMMAND ----------

# Run the export, catching any CloudWatch API error (Requirement 1.3).
_record_count: Optional[int] = None
_error_msg:    Optional[str] = None
_status = "failed"

try:
    _record_count = export_bronze_window(
        log_group=_log_group,
        start_ms=_start_ms,
        end_ms=_end_ms,
        aws_region=_aws_region,
    )
    _status = "success"
except Exception as exc:
    # On CloudWatch API error:
    #   - do NOT write Bronze rows (export_bronze_window raises before any write)
    #   - capture error message for checkpoint
    #   - status remains 'failed'
    _error_msg = str(exc)
    logger.error(
        "CW export failed for %s: %s", _log_group, _error_msg, exc_info=True
    )

# COMMAND ----------

# Always write a checkpoint (Requirement 8.3), whether success or failure.
_write_checkpoint(
    batch_id=_batch_id,
    start_time=_start_time,
    record_count=_record_count,
    status=_status,
    error_message=_error_msg,
)

# COMMAND ----------
# MAGIC %md ## 8. Run summary

# COMMAND ----------

print("=" * 60)
print(f"00_cw_export run complete")
print(f"  batch_id    : {_batch_id}")
print(f"  log_group   : {_log_group}")
print(f"  window_start: {datetime.fromtimestamp(_start_ms/1000, tz=timezone.utc).isoformat()}")
print(f"  window_end  : {datetime.fromtimestamp(_end_ms/1000,   tz=timezone.utc).isoformat()}")
print(f"  status      : {_status}")
print(f"  records     : {_record_count if _record_count is not None else 'N/A (failed)'}")
if _error_msg:
    print(f"  error       : {_error_msg}")
print("=" * 60)

# Surface the failure so the Databricks UI marks the job run as failed when
# the CloudWatch export itself encountered an error.
if _status == "failed":
    raise RuntimeError(
        f"[00_cw_export] Export failed for log_group={_log_group!r}: {_error_msg}"
    )
