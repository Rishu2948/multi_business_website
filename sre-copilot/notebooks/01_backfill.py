# Databricks notebook source
# Community Edition compatible — two-part table names (no Unity Catalog)
# Requirements: 1.4, 8.3

# COMMAND ----------
# MAGIC %md
# MAGIC # SRE Copilot — 30-Day Historical Backfill (`01_backfill.py`)
# MAGIC
# MAGIC **Run once** after `04_create_tables.py` to populate `bronze.app_logs` with up to
# MAGIC 30 days of historical CloudWatch log data.
# MAGIC
# MAGIC ### What this notebook does
# MAGIC - Reads the CloudWatch log group name from the `LOG_GROUP_NAME` widget.
# MAGIC - Iterates over **30 days × 4 six-hour windows = 120 windows** (oldest → newest).
# MAGIC - For each window:
# MAGIC   - Calls the CloudWatch Logs `filter_log_events` API via boto3.
# MAGIC   - **Zero events** → writes `status='empty_batch'` checkpoint, continues.
# MAGIC   - **Events found** → deduplicates on the composite key, writes to `bronze.app_logs`,
# MAGIC     writes `status='success'` checkpoint.
# MAGIC   - **API / write error** → writes `status='failed'` checkpoint, continues (does
# MAGIC     **not** abort the entire backfill).
# MAGIC - Prints a final summary of succeeded / empty / failed window counts.
# MAGIC
# MAGIC ### Prerequisites
# MAGIC 1. `04_create_tables.py` has been run (databases and tables exist).
# MAGIC 2. AWS credentials available to the cluster (instance-profile or Databricks secret scope).
# MAGIC 3. The `LOG_GROUP_NAME` widget value is set to your CloudWatch log group
# MAGIC    (e.g., `/aws/lambda/checkout-service`).

# COMMAND ----------
# MAGIC %md ## 0. Widget Parameters

# COMMAND ----------

dbutils.widgets.text(
    "LOG_GROUP_NAME",
    "/aws/lambda/my-service",
    "CloudWatch Log Group Name"
)

LOG_GROUP_NAME = dbutils.widgets.get("LOG_GROUP_NAME")
print(f"Log group: {LOG_GROUP_NAME}")

# COMMAND ----------
# MAGIC %md ## 1. Imports and Configuration

# COMMAND ----------

import boto3
import time
import traceback
from datetime import datetime, timezone, timedelta

from pyspark.sql import Row
from pyspark.sql.functions import col, lit
from pyspark.sql.types import (
    StructType, StructField,
    StringType, LongType
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NOTEBOOK_NAME    = "01_backfill"
BRONZE_TABLE     = "bronze.app_logs"
CHECKPOINT_TABLE = "config.pipeline_checkpoints"

# Number of days to backfill and the size of each time window
BACKFILL_DAYS    = 30
WINDOW_HOURS     = 6                        # 4 windows per day → 120 windows total
TOTAL_WINDOWS    = BACKFILL_DAYS * (24 // WINDOW_HOURS)   # 120

# CloudWatch Logs API page limit (max allowed by AWS)
CW_MAX_EVENTS_PER_PAGE = 10_000

# Bronze table schema (matches DDL in 04_create_tables.py)
BRONZE_SCHEMA = StructType([
    StructField("_raw",         StringType(), nullable=False),
    StructField("_time",        LongType(),   nullable=False),
    StructField("log_group",    StringType(), nullable=False),
    StructField("log_stream",   StringType(), nullable=False),
    StructField("source",       StringType(), nullable=True),
    StructField("host",         StringType(), nullable=True),
    StructField("_ingested_at", LongType(),   nullable=False),
    StructField("_batch_id",    StringType(), nullable=False),
])

print(f"Backfill configuration: {BACKFILL_DAYS} days × {WINDOW_HOURS}h windows "
      f"= {TOTAL_WINDOWS} windows total")

# COMMAND ----------
# MAGIC %md ## 2. Helper Functions

# COMMAND ----------

def _derive_source(log_group: str) -> str:
    """
    Derive a human-readable source label from the CloudWatch log group name.

    Examples:
      /aws/lambda/checkout-service  →  checkout-service
      /ecs/payment-service          →  payment-service
      /my-app/prod                  →  /my-app/prod   (fallback: the full name)
    """
    if log_group:
        parts = log_group.rstrip("/").split("/")
        return parts[-1] if parts else log_group
    return log_group


def _derive_host(log_stream: str) -> str:
    """
    Derive a host identifier from the CloudWatch log stream name.

    Log stream names often follow patterns such as:
      ecs/container/abc123   →  abc123
      i-0a1b2c3d4e5f        →  i-0a1b2c3d4e5f  (passthrough)
    """
    if log_stream:
        parts = log_stream.rstrip("/").split("/")
        return parts[-1] if parts else log_stream
    return log_stream


def export_window(log_group: str, start_ms: int, end_ms: int, batch_id: str):
    """
    Pull all log events in [start_ms, end_ms) from CloudWatch and return a
    list of dicts ready to be converted into Bronze rows.

    Handles CloudWatch pagination automatically (nextToken loop).

    Parameters
    ----------
    log_group : str   CloudWatch log group name.
    start_ms  : int   Window start time, Unix epoch milliseconds (inclusive).
    end_ms    : int   Window end time,  Unix epoch milliseconds (exclusive).
    batch_id  : str   Identifier for this export batch (written to _batch_id).

    Returns
    -------
    list[dict]   One dict per CloudWatch log event; empty list if no events found.

    Raises
    ------
    Exception   Propagates any boto3 / network error to the caller so it can
                write a 'failed' checkpoint.
    """
    cw_client    = boto3.client("logs")
    ingested_at  = int(time.time() * 1000)
    source       = _derive_source(log_group)
    rows         = []
    kwargs       = {
        "logGroupName": log_group,
        "startTime":    start_ms,
        "endTime":      end_ms,
        "limit":        CW_MAX_EVENTS_PER_PAGE,
    }

    while True:
        response = cw_client.filter_log_events(**kwargs)
        events   = response.get("events", [])

        for event in events:
            rows.append({
                "_raw":         event.get("message", ""),
                "_time":        event.get("timestamp", 0),
                "log_group":    log_group,
                "log_stream":   event.get("logStreamName", ""),
                "source":       source,
                "host":         _derive_host(event.get("logStreamName", "")),
                "_ingested_at": ingested_at,
                "_batch_id":    batch_id,
            })

        next_token = response.get("nextToken")
        if not next_token:
            break
        kwargs["nextToken"] = next_token

    return rows


def write_checkpoint(
    batch_id:      str,
    notebook:      str,
    record_count:  int,
    start_time:    datetime,
    end_time:      datetime,
    status:        str,
    error_message: str = None,
):
    """
    Write a single-row checkpoint to ``config.pipeline_checkpoints``.

    Failures are caught and printed to stdout so they never raise an exception
    that would propagate to the caller (Requirement 8.5).
    """
    try:
        row = Row(
            batch_id      = batch_id,
            notebook      = notebook,
            record_count  = record_count,
            start_time    = start_time,
            end_time      = end_time,
            status        = status,
            error_message = error_message,
        )
        df = spark.createDataFrame([row])
        df.write.format("delta").mode("append").saveAsTable(CHECKPOINT_TABLE)
    except Exception as cp_err:
        # Log to stdout but NEVER raise — a failed checkpoint write must not
        # abort the backfill job (Requirement 8.5)
        print(f"[WARN] Checkpoint write failed for batch_id={batch_id}: {cp_err}")


def write_bronze_rows(rows: list, batch_id: str) -> int:
    """
    Deduplicate *rows* on the composite key
    (log_group, log_stream, _time, _raw) and merge-write to
    ``bronze.app_logs`` via Delta's ``dropDuplicates`` + append.

    Returns the number of rows actually written after deduplication.
    """
    df = spark.createDataFrame(rows, schema=BRONZE_SCHEMA)
    dedup_df = df.dropDuplicates(["log_group", "log_stream", "_time", "_raw"])
    written  = dedup_df.count()

    (
        dedup_df
        .write
        .format("delta")
        .mode("append")
        .saveAsTable(BRONZE_TABLE)
    )
    return written

# COMMAND ----------
# MAGIC %md ## 3. Compute Window Boundaries

# COMMAND ----------

# Anchor the backfill at "now" so that the final window ends at the current UTC time.
now_utc      = datetime.now(timezone.utc)
backfill_end = now_utc.replace(minute=0, second=0, microsecond=0)   # floor to the hour

# Start of the backfill: BACKFILL_DAYS days before the end time
backfill_start = backfill_end - timedelta(days=BACKFILL_DAYS)

# Build the list of (window_start, window_end) pairs, oldest first
windows = []
cursor  = backfill_start
while cursor < backfill_end:
    win_end = min(cursor + timedelta(hours=WINDOW_HOURS), backfill_end)
    windows.append((cursor, win_end))
    cursor = win_end

actual_windows = len(windows)
print(f"Backfill range : {backfill_start.isoformat()} → {backfill_end.isoformat()}")
print(f"Window count   : {actual_windows}  (target: {TOTAL_WINDOWS})")

# COMMAND ----------
# MAGIC %md ## 4. Main Backfill Loop

# COMMAND ----------

# Counters for the final summary
count_success    = 0
count_empty      = 0
count_failed     = 0

print(f"\n{'='*70}")
print(f"Starting backfill of '{LOG_GROUP_NAME}' — {actual_windows} windows")
print(f"{'='*70}\n")

for idx, (win_start, win_end) in enumerate(windows, start=1):
    # -----------------------------------------------------------------------
    # Build a human-readable batch_id: "backfill-YYYYMMDD-HH"
    # -----------------------------------------------------------------------
    batch_id   = f"backfill-{win_start.strftime('%Y%m%d-%H')}"
    start_ms   = int(win_start.timestamp() * 1000)
    end_ms     = int(win_end.timestamp()   * 1000)

    progress_pct = (idx / actual_windows) * 100
    print(
        f"[{idx:>3}/{actual_windows}  {progress_pct:5.1f}%]  "
        f"{win_start.strftime('%Y-%m-%d %H:%M')} → "
        f"{win_end.strftime('%Y-%m-%d %H:%M')}  batch_id={batch_id}"
    )

    # -----------------------------------------------------------------------
    # Attempt to fetch and write events for this window
    # -----------------------------------------------------------------------
    try:
        rows = export_window(LOG_GROUP_NAME, start_ms, end_ms, batch_id)

        if len(rows) == 0:
            # ----------------------------------------------------------------
            # Zero-event window: write empty_batch checkpoint, continue
            # Requirement 1.4 — "log a checkpoint entry with status='empty_batch'
            #                    and continue to the next increment without error"
            # ----------------------------------------------------------------
            write_checkpoint(
                batch_id      = batch_id,
                notebook      = NOTEBOOK_NAME,
                record_count  = 0,
                start_time    = win_start,
                end_time      = win_end,
                status        = "empty_batch",
                error_message = None,
            )
            count_empty += 1
            print(f"         → empty_batch (0 events)")

        else:
            # ----------------------------------------------------------------
            # Events found: write Bronze rows, then write success checkpoint
            # ----------------------------------------------------------------
            written = write_bronze_rows(rows, batch_id)
            write_checkpoint(
                batch_id      = batch_id,
                notebook      = NOTEBOOK_NAME,
                record_count  = written,
                start_time    = win_start,
                end_time      = win_end,
                status        = "success",
                error_message = None,
            )
            count_success += 1
            print(
                f"         → success  ({len(rows)} fetched, "
                f"{written} written after dedup)"
            )

    except Exception as err:
        # ------------------------------------------------------------------
        # Error handling: write failed checkpoint, do NOT abort the backfill
        # Requirement 8.3 — "write a checkpoint entry … status='failed'"
        # ------------------------------------------------------------------
        tb_str = traceback.format_exc()
        write_checkpoint(
            batch_id      = batch_id,
            notebook      = NOTEBOOK_NAME,
            record_count  = 0,
            start_time    = win_start,
            end_time      = win_end,
            status        = "failed",
            error_message = str(err)[:2048],   # truncate to avoid oversized rows
        )
        count_failed += 1
        print(f"         → failed  — {err}")
        print(f"         Traceback:\n{tb_str}")
        # Continue to next window — do NOT re-raise

# COMMAND ----------
# MAGIC %md ## 5. Backfill Summary

# COMMAND ----------

total_processed = count_success + count_empty + count_failed

print(f"\n{'='*70}")
print(f"Backfill complete — {LOG_GROUP_NAME}")
print(f"{'='*70}")
print(f"  Total windows : {actual_windows}")
print(f"  ✓ success     : {count_success}")
print(f"  ○ empty_batch : {count_empty}")
print(f"  ✗ failed      : {count_failed}")
print(f"  Processed     : {total_processed}")
print(f"{'='*70}\n")

if count_failed > 0:
    print(
        f"[WARN] {count_failed} window(s) failed. "
        f"Review config.pipeline_checkpoints WHERE status='failed' AND "
        f"notebook='{NOTEBOOK_NAME}' for details."
    )
else:
    print("[INFO] All windows completed without error.")

if count_success == 0 and count_failed == 0:
    print(
        f"[INFO] No events found in any window. "
        f"Verify the log group name '{LOG_GROUP_NAME}' and AWS credential setup."
    )

# COMMAND ----------
# MAGIC %md
# MAGIC ## Next Steps
# MAGIC
# MAGIC After this backfill completes:
# MAGIC
# MAGIC 1. Run `02_bronze_to_silver.py` to promote Bronze records to the Silver layer.
# MAGIC 2. Run `03_silver_to_gold.py` to build Gold aggregations and health scores.
# MAGIC 3. Schedule `00_cw_export.py` for continuous ingestion of new logs.
# MAGIC
# MAGIC To inspect checkpoint results:
# MAGIC ```sql
# MAGIC SELECT *
# MAGIC FROM   config.pipeline_checkpoints
# MAGIC WHERE  notebook = '01_backfill'
# MAGIC ORDER  BY start_time DESC
# MAGIC LIMIT  20;
# MAGIC ```
