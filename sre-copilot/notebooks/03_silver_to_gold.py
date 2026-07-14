# Databricks notebook source
# Community Edition compatible — two-part table names (no Unity Catalog)
# Requirements: 3.1, 3.2, 3.3, 3.5, 3.6, 8.3, 8.4, 8.5

# COMMAND ----------
# MAGIC %md
# MAGIC # SRE Copilot — Silver → Gold Aggregation (`03_silver_to_gold.py`)
# MAGIC
# MAGIC **Purpose:** Aggregate cleaned `silver.logs` records into pre-computed Gold tables
# MAGIC consumed by the Bedrock Agent's Lambda tools.
# MAGIC
# MAGIC **Outputs:**
# MAGIC - `gold.error_summaries` — hourly per-service/region error counts, anomaly flags,
# MAGIC   top error types, trend direction, and natural-language summaries (≤ 500 chars)
# MAGIC - `gold.service_health` — four-band health score (100/75/50/25) and status per
# MAGIC   service/region/hour
# MAGIC - `gold.error_patterns` — top 10 error patterns per service ranked by 24h occurrences
# MAGIC
# MAGIC **Incremental write strategy:** `replaceWhere` scoped to the last 3 hours to avoid
# MAGIC full-table rewrites on Community Edition single-node clusters (Requirement 3.5).
# MAGIC
# MAGIC **Stale-source detection:** If `bronze.app_logs` has had no new data in > 2 hours,
# MAGIC writes a `status='stale_source'` checkpoint and continues without raising an exception
# MAGIC (Requirements 8.4, 8.5).
# MAGIC
# MAGIC **Tables read:**    `silver.logs`, `bronze.app_logs`
# MAGIC **Tables written:** `gold.error_summaries`, `gold.service_health`,
# MAGIC                     `gold.error_patterns`, `config.pipeline_checkpoints`
# MAGIC
# MAGIC **Requirements:** 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 8.3, 8.4, 8.5

# COMMAND ----------
# MAGIC %md ## 1. Imports and Spark session

# COMMAND ----------

import hashlib
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    BigIntType,
    BooleanType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

spark = SparkSession.getActiveSession()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("03_silver_to_gold")

# COMMAND ----------
# MAGIC %md ## 2. Configuration

# COMMAND ----------

# Window for incremental `replaceWhere` writes (Requirement 3.5)
_REPLACE_HOURS = 3

# Anomaly threshold: error_rate_vs_normal > 2.0 → is_anomalous = True (Req 3.2)
_ANOMALY_THRESHOLD = 2.0

# Trend direction thresholds
_TREND_DEGRADING  = 1.2
_TREND_IMPROVING  = 0.8

# Rolling baseline window in days (Req 3.2)
_BASELINE_DAYS = 7

# Top N error types per summary row
_TOP_ERROR_TYPES_N = 3

# Top N patterns per service for gold.error_patterns (Req 3.4)
_TOP_PATTERNS_N = 10

# Stale Bronze threshold: no new data in > 2 hours (Req 8.4)
_STALE_BRONZE_HOURS = 2

# Natural-language summary max length (Req 3.1)
_NL_SUMMARY_MAX_LEN = 500

# COMMAND ----------
# MAGIC %md ## 3. Helper: checkpoint writer

# COMMAND ----------


def _write_checkpoint(
    batch_id: str,
    start_time: datetime,
    record_count: Optional[int],
    status: str,
    error_message: Optional[str] = None,
    notebook: str = "03_silver_to_gold",
) -> None:
    """
    Append a single row to ``config.pipeline_checkpoints``.

    If the write itself fails, logs to stdout and does NOT raise an exception
    (Requirements 8.3, 8.5).
    """
    end_time = datetime.now(timezone.utc)
    try:
        df = (
            spark.createDataFrame(
                [(
                    batch_id,
                    notebook,
                    record_count,
                    start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    status,
                    error_message,
                )],
                schema=[
                    "batch_id", "notebook", "record_count",
                    "start_time", "end_time", "status", "error_message",
                ],
            )
            .withColumn("start_time",   F.to_timestamp("start_time"))
            .withColumn("end_time",     F.to_timestamp("end_time"))
            .withColumn("record_count", F.col("record_count").cast("long"))
        )
        df.write.format("delta").mode("append").saveAsTable(
            "config.pipeline_checkpoints"
        )
        logger.info(
            "Checkpoint written: batch_id=%s status=%s", batch_id, status
        )
    except Exception as cp_err:
        # Requirement 8.5: log to stdout; do NOT raise
        print(
            f"[03_silver_to_gold] WARNING: checkpoint write failed — {cp_err}"
        )

# COMMAND ----------
# MAGIC %md ## 4. Stale Bronze detection (Requirements 8.4, 8.5)

# COMMAND ----------


def _check_bronze_staleness(run_start: datetime, batch_id: str) -> bool:
    """
    Return True when ``bronze.app_logs`` has had no new ingestion in the last
    ``_STALE_BRONZE_HOURS`` hours.

    Writes a ``status='stale_source'`` checkpoint on staleness and logs a
    warning.  Does NOT raise an exception in either case (Requirement 8.5).
    """
    try:
        row = spark.sql(
            "SELECT MAX(_ingested_at) AS max_ingested FROM bronze.app_logs"
        ).first()

        if row is None or row["max_ingested"] is None:
            logger.warning(
                "bronze.app_logs appears to be empty — treating as stale."
            )
            _write_checkpoint(
                batch_id=batch_id,
                start_time=run_start,
                record_count=0,
                status="stale_source",
                error_message="bronze.app_logs is empty",
            )
            return True

        # _ingested_at is stored as epoch milliseconds (BIGINT)
        max_ingested_ms: int = row["max_ingested"]
        max_ingested_dt = datetime.fromtimestamp(
            max_ingested_ms / 1000, tz=timezone.utc
        )
        age_hours = (run_start - max_ingested_dt).total_seconds() / 3600

        if age_hours > _STALE_BRONZE_HOURS:
            msg = (
                f"Bronze last ingested {age_hours:.1f}h ago "
                f"(threshold {_STALE_BRONZE_HOURS}h)"
            )
            logger.warning("STALE SOURCE detected: %s", msg)
            print(f"[03_silver_to_gold] WARNING: {msg}")
            _write_checkpoint(
                batch_id=batch_id,
                start_time=run_start,
                record_count=None,
                status="stale_source",
                error_message=msg,
            )
            return True

        logger.info(
            "Bronze freshness OK — last ingestion %.1f hours ago.", age_hours
        )
        return False

    except Exception as exc:
        # If we cannot check staleness (e.g., table doesn't exist yet), log and
        # continue — never fail the Gold job because of this check.
        print(
            f"[03_silver_to_gold] WARNING: staleness check failed — {exc}"
        )
        return False

# COMMAND ----------
# MAGIC %md ## 5. NL summary builder
# MAGIC
# MAGIC Generates a ≤ 500-character human-readable summary for each aggregation row
# MAGIC (Requirement 3.1).

# COMMAND ----------


def _build_nl_summary(
    service: str,
    region: str,
    total_errors: int,
    total_warnings: int,
    error_rate_vs_normal: float,
    is_anomalous: bool,
) -> str:
    """
    Build a natural-language summary string capped at _NL_SUMMARY_MAX_LEN characters.

    Format:
      "Service {service} in {region}: {total_errors} errors, {total_warnings} warnings.
       Rate vs normal: {error_rate_vs_normal:.1f}x. {'ANOMALY DETECTED' | 'Within normal range'}."

    Requirements: 3.1
    """
    anomaly_text = "ANOMALY DETECTED" if is_anomalous else "Within normal range"
    summary = (
        f"Service {service} in {region}: "
        f"{total_errors} errors, {total_warnings} warnings. "
        f"Rate vs normal: {error_rate_vs_normal:.1f}x. "
        f"{anomaly_text}."
    )
    # Truncate if needed to satisfy the ≤ 500 char requirement
    if len(summary) > _NL_SUMMARY_MAX_LEN:
        summary = summary[: _NL_SUMMARY_MAX_LEN - 1] + "…"
    return summary


_build_nl_summary_udf = F.udf(_build_nl_summary, StringType())

# COMMAND ----------
# MAGIC %md ## 6. Health score mapper
# MAGIC
# MAGIC Four-band formula (Requirement 3.3):
# MAGIC
# MAGIC | `error_rate_vs_normal` | `overall_health` | `status` |
# MAGIC |---|---|---|
# MAGIC | ≤ 1.0 | 100 | healthy |
# MAGIC | (1.0, 2.0] | 75 | degraded |
# MAGIC | (2.0, 5.0] | 50 | degraded |
# MAGIC | > 5.0 | 25 | critical |

# COMMAND ----------


def _health_score(rate: Optional[float]) -> float:
    """Return the health score for a given error_rate_vs_normal value."""
    if rate is None or rate <= 1.0:
        return 100.0
    if rate <= 2.0:
        return 75.0
    if rate <= 5.0:
        return 50.0
    return 25.0


def _health_status(rate: Optional[float]) -> str:
    """Return the health status string for a given error_rate_vs_normal value."""
    if rate is None or rate <= 1.0:
        return "healthy"
    if rate <= 5.0:
        return "degraded"
    return "critical"


_health_score_udf  = F.udf(_health_score, DoubleType())
_health_status_udf = F.udf(_health_status, StringType())

# COMMAND ----------
# MAGIC %md ## 7. Trend direction
# MAGIC
# MAGIC - `'degrading'`  when `error_rate_vs_normal > 1.2`
# MAGIC - `'improving'`  when `error_rate_vs_normal < 0.8`
# MAGIC - `'stable'`     otherwise

# COMMAND ----------


def _trend_direction(rate: Optional[float]) -> str:
    """Return trend direction label."""
    if rate is None:
        return "stable"
    if rate > _TREND_DEGRADING:
        return "degrading"
    if rate < _TREND_IMPROVING:
        return "improving"
    return "stable"


_trend_direction_udf = F.udf(_trend_direction, StringType())

# COMMAND ----------
# MAGIC %md ## 8. Gold error summaries aggregation
# MAGIC
# MAGIC Reads `silver.logs`, computes hourly per-service/region aggregations, and
# MAGIC writes to `gold.error_summaries` using `replaceWhere` scoped to the last 3 hours.

# COMMAND ----------


def _build_error_summaries(run_start: datetime) -> DataFrame:
    """
    Aggregate silver.logs into the gold.error_summaries schema.

    Steps:
    1. Truncate `timestamp` to the hour.
    2. Count errors (level='ERROR') and warnings (level='WARN').
    3. Compute the 7-day rolling baseline using available-day denominator.
    4. Compute error_rate_vs_normal, is_anomalous, top_error_types, trend_direction,
       and nl_summary.

    Returns a DataFrame matching the gold.error_summaries schema.

    Requirements: 3.1, 3.2, 3.5
    """
    # ------------------------------------------------------------------ #
    # 8a. Current-hour window (last _REPLACE_HOURS hours for replaceWhere) #
    # ------------------------------------------------------------------ #
    window_start = run_start - timedelta(hours=_REPLACE_HOURS)
    window_start_str = window_start.strftime("%Y-%m-%d %H:%M:%S")

    df_silver = spark.table("silver.logs")

    # ------------------------------------------------------------------ #
    # 8b. Current-hour aggregation                                         #
    # ------------------------------------------------------------------ #
    df_current = (
        df_silver
        .filter(F.col("timestamp") >= F.lit(window_start_str).cast("timestamp"))
        .withColumn("hour", F.date_trunc("hour", F.col("timestamp")))
        .groupBy("hour", "service", "region")
        .agg(
            F.sum(
                F.when(F.col("level") == "ERROR", 1).otherwise(0)
            ).alias("total_errors"),
            F.sum(
                F.when(F.col("level") == "WARN", 1).otherwise(0)
            ).alias("total_warnings"),
        )
    )

    # ------------------------------------------------------------------ #
    # 8c. 7-day rolling baseline                                           #
    #                                                                      #
    # For each (service, region) we count errors over the prior 7 days    #
    # and divide by the number of distinct calendar days with data (not   #
    # hard-coded 7) to get the average per-hour rate.  This satisfies     #
    # the available-day denominator rule (Requirement 3.2).               #
    # ------------------------------------------------------------------ #
    baseline_end   = window_start  # baseline ends before the current window
    baseline_start = baseline_end - timedelta(days=_BASELINE_DAYS)
    baseline_start_str = baseline_start.strftime("%Y-%m-%d %H:%M:%S")
    baseline_end_str   = baseline_end.strftime("%Y-%m-%d %H:%M:%S")

    df_baseline = (
        df_silver
        .filter(
            (F.col("timestamp") >= F.lit(baseline_start_str).cast("timestamp"))
            & (F.col("timestamp") < F.lit(baseline_end_str).cast("timestamp"))
            & (F.col("level") == "ERROR")
        )
        .groupBy("service", "region")
        .agg(
            # Total errors in the baseline window
            F.count("*").alias("baseline_total_errors"),
            # Number of distinct calendar days that have at least one record
            F.countDistinct(F.to_date("timestamp")).alias("distinct_days"),
            # Total number of distinct hours with data (for per-hour avg)
            F.countDistinct(
                F.date_trunc("hour", F.col("timestamp"))
            ).alias("distinct_hours"),
        )
        # avg errors per hour = total_errors / distinct_hours
        # (fall back to 1 distinct hour to avoid division-by-zero)
        .withColumn(
            "baseline_avg_per_hour",
            F.col("baseline_total_errors") / F.greatest(
                F.col("distinct_hours"), F.lit(1)
            ),
        )
    )

    # ------------------------------------------------------------------ #
    # 8d. Join current aggregation with baseline                           #
    # ------------------------------------------------------------------ #
    df_joined = df_current.join(
        df_baseline.select(
            "service", "region", "baseline_avg_per_hour", "distinct_days"
        ),
        on=["service", "region"],
        how="left",
    )

    # error_rate_vs_normal: current ÷ baseline (default 1.0 when baseline = 0)
    df_joined = df_joined.withColumn(
        "error_rate_vs_normal",
        F.when(
            F.col("baseline_avg_per_hour").isNull()
            | (F.col("baseline_avg_per_hour") == 0.0),
            F.lit(1.0),
        ).otherwise(
            F.col("total_errors") / F.col("baseline_avg_per_hour")
        ),
    )

    # ------------------------------------------------------------------ #
    # 8e. is_anomalous, trend_direction                                    #
    # ------------------------------------------------------------------ #
    df_joined = df_joined.withColumn(
        "is_anomalous",
        F.col("error_rate_vs_normal") > F.lit(_ANOMALY_THRESHOLD),
    )

    df_joined = df_joined.withColumn(
        "trend_direction",
        _trend_direction_udf(F.col("error_rate_vs_normal")),
    )

    # ------------------------------------------------------------------ #
    # 8f. Top 3 error types per (hour, service, region)                   #
    # ------------------------------------------------------------------ #
    # Collect error types from the current window with counts
    df_error_types = (
        df_silver
        .filter(
            (F.col("timestamp") >= F.lit(window_start_str).cast("timestamp"))
            & (F.col("level") == "ERROR")
        )
        .withColumn("hour", F.date_trunc("hour", F.col("timestamp")))
        .groupBy("hour", "service", "region", "error_type", "error_category")
        .agg(
            F.count("*").alias("et_count"),
            F.first("message").alias("sample_message"),
        )
    )

    # Window to rank error types within each (hour, service, region) bucket
    w_et = Window.partitionBy("hour", "service", "region").orderBy(
        F.col("et_count").desc()
    )
    df_error_types_ranked = (
        df_error_types
        .withColumn("et_rank", F.row_number().over(w_et))
        .filter(F.col("et_rank") <= _TOP_ERROR_TYPES_N)
    )

    # Compute total errors per (hour, service, region) for pct calculation
    df_error_types_ranked = df_error_types_ranked.withColumn(
        "pct",
        F.col("et_count").cast("double") / F.greatest(
            F.sum("et_count").over(
                Window.partitionBy("hour", "service", "region")
            ),
            F.lit(1),
        ),
    )

    # Aggregate into an array of structs
    top_error_type_schema = ArrayType(
        StructType([
            StructField("error_type",     StringType(), True),
            StructField("category",       StringType(), True),
            StructField("count",          LongType(),   True),
            StructField("pct",            DoubleType(), True),
            StructField("sample_message", StringType(), True),
        ])
    )

    df_top_errors = (
        df_error_types_ranked
        .groupBy("hour", "service", "region")
        .agg(
            F.collect_list(
                F.struct(
                    F.col("error_type").alias("error_type"),
                    F.col("error_category").alias("category"),
                    F.col("et_count").cast("long").alias("count"),
                    F.col("pct").alias("pct"),
                    F.col("sample_message").alias("sample_message"),
                )
            ).alias("top_error_types")
        )
    )

    # ------------------------------------------------------------------ #
    # 8g. Join top error types back                                        #
    # ------------------------------------------------------------------ #
    df_joined = df_joined.join(
        df_top_errors,
        on=["hour", "service", "region"],
        how="left",
    )

    # ------------------------------------------------------------------ #
    # 8h. NL summary (Requirement 3.1)                                     #
    # ------------------------------------------------------------------ #
    df_joined = df_joined.withColumn(
        "nl_summary",
        _build_nl_summary_udf(
            F.col("service"),
            F.col("region"),
            F.col("total_errors"),
            F.col("total_warnings"),
            F.col("error_rate_vs_normal"),
            F.col("is_anomalous"),
        ),
    )

    # ------------------------------------------------------------------ #
    # 8i. Select final schema                                              #
    # ------------------------------------------------------------------ #
    df_result = df_joined.select(
        F.col("hour"),
        F.col("service"),
        F.col("region"),
        F.col("total_errors").cast("long"),
        F.col("total_warnings").cast("long"),
        F.col("error_rate_vs_normal").cast("double"),
        F.col("is_anomalous"),
        F.col("top_error_types"),
        F.col("trend_direction"),
        F.col("nl_summary"),
    )

    return df_result

# COMMAND ----------
# MAGIC %md ## 9. Gold service health aggregation
# MAGIC
# MAGIC Derives `gold.service_health` from the already-computed error summaries
# MAGIC using the four-band formula (Requirement 3.3).

# COMMAND ----------


def _build_service_health(df_summaries: DataFrame) -> DataFrame:
    """
    Derive gold.service_health from the error_summaries DataFrame.

    Requirements: 3.3
    """
    return (
        df_summaries
        .select(
            F.col("hour").alias("timestamp_hour"),
            F.col("service"),
            F.col("region"),
            _health_score_udf(F.col("error_rate_vs_normal")).alias("overall_health"),
            _health_status_udf(F.col("error_rate_vs_normal")).alias("status"),
        )
    )

# COMMAND ----------
# MAGIC %md ## 10. Sentinel rows for absent Silver data (Requirement 3.6)
# MAGIC
# MAGIC When `silver.logs` is empty (or has no records in the current window),
# MAGIC write a sentinel row with `total_errors=0`, `status='healthy'`.

# COMMAND ----------


def _build_sentinel_summaries(run_start: datetime) -> DataFrame:
    """
    Build a minimal sentinel DataFrame for gold.error_summaries when no Silver
    data is present.

    The sentinel row uses the current truncated hour and a placeholder service/region.
    In practice the caller should only invoke this when Silver is confirmed empty.

    Requirements: 3.6
    """
    current_hour = run_start.replace(
        minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%d %H:%M:%S")

    sentinel_summary_schema = StructType([
        StructField("hour",                 TimestampType(), False),
        StructField("service",              StringType(),    False),
        StructField("region",               StringType(),    False),
        StructField("total_errors",         LongType(),      False),
        StructField("total_warnings",       LongType(),      False),
        StructField("error_rate_vs_normal", DoubleType(),    False),
        StructField("is_anomalous",         BooleanType(),   False),
        StructField("top_error_types",      StringType(),    True),   # null array
        StructField("trend_direction",      StringType(),    True),
        StructField("nl_summary",           StringType(),    True),
    ])

    df = spark.createDataFrame(
        [(current_hour, "unknown", "us-west-2", 0, 0, 1.0, False, None, "stable",
          "No Silver data available for this window.")],
        schema=["hour", "service", "region", "total_errors", "total_warnings",
                "error_rate_vs_normal", "is_anomalous", "top_error_types",
                "trend_direction", "nl_summary"],
    ).withColumn("hour", F.to_timestamp("hour"))

    return df


def _build_sentinel_health(run_start: datetime) -> DataFrame:
    """
    Build a minimal sentinel DataFrame for gold.service_health.

    Requirements: 3.6
    """
    current_hour = run_start.replace(
        minute=0, second=0, microsecond=0
    ).strftime("%Y-%m-%d %H:%M:%S")

    df = spark.createDataFrame(
        [(current_hour, "unknown", "us-west-2", 100.0, "healthy")],
        schema=["timestamp_hour", "service", "region", "overall_health", "status"],
    ).withColumn("timestamp_hour", F.to_timestamp("timestamp_hour"))

    return df

# COMMAND ----------
# MAGIC %md ## 11. Gold error patterns aggregation (Requirement 3.4)

# COMMAND ----------


def _build_error_patterns(run_start: datetime) -> DataFrame:
    """
    Cluster silver.logs by (error_type, error_category) to produce
    gold.error_patterns.

    Computes:
    - occurrences_24h: count of matching records in the last 24 hours
    - trend_7d: ratio of occurrences_24h to average daily occurrences
                over the prior 7 days
    - is_new_pattern: True when the pattern's first-seen time is < 24h ago
    - pattern_id: SHA-256(service || error_type || error_category)
    - last_seen, updated_at: timestamps from aggregation
    - canonical_message: representative (first) sample message
    - known_resolution: null (populated manually or from runbooks)

    Top 10 patterns per service ranked by occurrences_24h DESC (Req 3.4).

    Requirements: 3.4
    """
    now_str       = run_start.strftime("%Y-%m-%d %H:%M:%S")
    last_24h_str  = (run_start - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    last_7d_str   = (run_start - timedelta(days=_BASELINE_DAYS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    df_silver = spark.table("silver.logs")

    # ------------------------------------------------------------------ #
    # 11a. 24-hour window counts                                           #
    # ------------------------------------------------------------------ #
    df_24h = (
        df_silver
        .filter(
            F.col("timestamp") >= F.lit(last_24h_str).cast("timestamp")
        )
        .groupBy("service", "error_type", "error_category")
        .agg(
            F.count("*").alias("occurrences_24h"),
            F.max("timestamp").alias("last_seen"),
            F.min("timestamp").alias("first_seen_24h"),
            F.first("message").alias("canonical_message"),
        )
    )

    # ------------------------------------------------------------------ #
    # 11b. 7-day baseline for trend_7d                                     #
    # ------------------------------------------------------------------ #
    df_7d = (
        df_silver
        .filter(
            (F.col("timestamp") >= F.lit(last_7d_str).cast("timestamp"))
            & (F.col("timestamp") < F.lit(last_24h_str).cast("timestamp"))
        )
        .groupBy("service", "error_type", "error_category")
        .agg(
            F.count("*").alias("total_prior_6d"),
            F.countDistinct(F.to_date("timestamp")).alias("prior_distinct_days"),
        )
        .withColumn(
            "daily_avg_prior",
            F.col("total_prior_6d") / F.greatest(
                F.col("prior_distinct_days"), F.lit(1)
            ),
        )
    )

    # ------------------------------------------------------------------ #
    # 11c. Join and compute trend_7d                                       #
    # ------------------------------------------------------------------ #
    df_joined = df_24h.join(
        df_7d.select(
            "service", "error_type", "error_category", "daily_avg_prior"
        ),
        on=["service", "error_type", "error_category"],
        how="left",
    )

    df_joined = df_joined.withColumn(
        "trend_7d",
        F.when(
            F.col("daily_avg_prior").isNull() | (F.col("daily_avg_prior") == 0.0),
            F.lit(1.0),
        ).otherwise(
            F.col("occurrences_24h").cast("double") / F.col("daily_avg_prior")
        ),
    )

    # is_new_pattern: first occurrence in the last 24h means we have no prior history
    df_joined = df_joined.withColumn(
        "is_new_pattern",
        F.col("daily_avg_prior").isNull() | (F.col("daily_avg_prior") == 0.0),
    )

    # ------------------------------------------------------------------ #
    # 11d. pattern_id = SHA-256(service || error_type || error_category)  #
    # ------------------------------------------------------------------ #
    def _pattern_id(
        service: Optional[str],
        error_type: Optional[str],
        error_category: Optional[str],
    ) -> str:
        svc = service or ""
        et  = error_type or ""
        ec  = error_category or ""
        return hashlib.sha256(
            (svc + et + ec).encode("utf-8")
        ).hexdigest()

    _pattern_id_udf = F.udf(_pattern_id, StringType())

    df_joined = df_joined.withColumn(
        "pattern_id",
        _pattern_id_udf(
            F.col("service"), F.col("error_type"), F.col("error_category")
        ),
    )

    # ------------------------------------------------------------------ #
    # 11e. Rank top _TOP_PATTERNS_N per service and select schema          #
    # ------------------------------------------------------------------ #
    w_rank = Window.partitionBy("service").orderBy(F.col("occurrences_24h").desc())
    df_ranked = (
        df_joined
        .withColumn("_rank", F.row_number().over(w_rank))
        .filter(F.col("_rank") <= _TOP_PATTERNS_N)
    )

    updated_at_ts = run_start.strftime("%Y-%m-%d %H:%M:%S")

    df_result = df_ranked.select(
        F.col("pattern_id"),
        F.col("service"),
        F.col("error_type"),
        F.col("error_category"),
        F.col("canonical_message"),
        F.col("occurrences_24h").cast("long"),
        F.col("trend_7d").cast("double"),
        F.col("is_new_pattern"),
        F.lit(None).cast("string").alias("known_resolution"),
        F.col("last_seen"),
        F.to_timestamp(F.lit(updated_at_ts)).alias("updated_at"),
    )

    return df_result

# COMMAND ----------
# MAGIC %md ## 12. Incremental write helpers (replaceWhere — Requirement 3.5)

# COMMAND ----------


def _write_error_summaries(df: DataFrame, run_start: datetime) -> int:
    """
    Write df to gold.error_summaries using replaceWhere scoped to the last
    _REPLACE_HOURS hours (Requirement 3.5).

    Returns the row count written.
    """
    window_start = run_start - timedelta(hours=_REPLACE_HOURS)
    predicate = (
        f"hour >= '{window_start.strftime('%Y-%m-%d %H:%M:%S')}'"
    )
    logger.info(
        "Writing gold.error_summaries with replaceWhere: %s", predicate
    )
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("replaceWhere", predicate)
        .option("mergeSchema", "true")
        .saveAsTable("gold.error_summaries")
    )
    count = df.count()
    logger.info("gold.error_summaries: %d rows written.", count)
    return count


def _write_service_health(df: DataFrame, run_start: datetime) -> int:
    """
    Write df to gold.service_health using replaceWhere scoped to the last
    _REPLACE_HOURS hours (Requirement 3.5).

    Returns the row count written.
    """
    window_start = run_start - timedelta(hours=_REPLACE_HOURS)
    predicate = (
        f"timestamp_hour >= '{window_start.strftime('%Y-%m-%d %H:%M:%S')}'"
    )
    logger.info(
        "Writing gold.service_health with replaceWhere: %s", predicate
    )
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("replaceWhere", predicate)
        .option("mergeSchema", "true")
        .saveAsTable("gold.service_health")
    )
    count = df.count()
    logger.info("gold.service_health: %d rows written.", count)
    return count


def _write_error_patterns(df: DataFrame) -> int:
    """
    Write df to gold.error_patterns (full overwrite — patterns are re-computed
    from scratch each run).

    Returns the row count written.
    """
    logger.info("Writing gold.error_patterns …")
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("mergeSchema", "true")
        .saveAsTable("gold.error_patterns")
    )
    count = df.count()
    logger.info("gold.error_patterns: %d rows written.", count)
    return count

# COMMAND ----------
# MAGIC %md ## 13. Main pipeline execution

# COMMAND ----------

_run_start   = datetime.now(timezone.utc)
_batch_id    = _run_start.strftime("gold-%Y%m%d-%H%M%S")
_status      = "failed"
_record_count: Optional[int] = None
_error_msg:   Optional[str]  = None

try:
    # ------------------------------------------------------------------ #
    # 13a. Stale Bronze check (Requirements 8.4, 8.5)                      #
    # ------------------------------------------------------------------ #
    # This check writes its own stale_source checkpoint if Bronze is stale,
    # then continues — the Gold job always proceeds regardless.
    _check_bronze_staleness(_run_start, _batch_id)

    # ------------------------------------------------------------------ #
    # 13b. Determine whether Silver has data for the current window        #
    # ------------------------------------------------------------------ #
    window_start = _run_start - timedelta(hours=_REPLACE_HOURS)
    window_start_str = window_start.strftime("%Y-%m-%d %H:%M:%S")

    df_silver_check = spark.table("silver.logs").filter(
        F.col("timestamp") >= F.lit(window_start_str).cast("timestamp")
    )
    silver_is_empty = df_silver_check.limit(1).count() == 0

    # ------------------------------------------------------------------ #
    # 13c. Build and write gold.error_summaries                            #
    # ------------------------------------------------------------------ #
    if silver_is_empty:
        logger.warning(
            "silver.logs is empty for the current window — writing sentinel rows."
        )
        df_summaries = _build_sentinel_summaries(_run_start)
    else:
        df_summaries = _build_error_summaries(_run_start)

    summaries_count = _write_error_summaries(df_summaries, _run_start)

    # ------------------------------------------------------------------ #
    # 13d. Build and write gold.service_health                             #
    # ------------------------------------------------------------------ #
    if silver_is_empty:
        df_health = _build_sentinel_health(_run_start)
    else:
        df_health = _build_service_health(df_summaries)

    health_count = _write_service_health(df_health, _run_start)

    # ------------------------------------------------------------------ #
    # 13e. Build and write gold.error_patterns                             #
    # ------------------------------------------------------------------ #
    if not silver_is_empty:
        df_patterns = _build_error_patterns(_run_start)
        patterns_count = _write_error_patterns(df_patterns)
    else:
        logger.info(
            "Skipping gold.error_patterns write — no Silver data in current window."
        )
        patterns_count = 0

    # ------------------------------------------------------------------ #
    # 13f. Aggregate total record count for checkpoint                     #
    # ------------------------------------------------------------------ #
    _record_count = summaries_count + health_count + patterns_count
    _status = "success"

    logger.info(
        "03_silver_to_gold complete: batch_id=%s summaries=%d health=%d patterns=%d",
        _batch_id, summaries_count, health_count, patterns_count,
    )

except Exception as exc:
    _error_msg = str(exc)
    logger.error(
        "03_silver_to_gold failed: %s", _error_msg, exc_info=True
    )

# COMMAND ----------
# MAGIC %md ## 14. Write main checkpoint (always — Requirement 8.3)

# COMMAND ----------

# Write final checkpoint regardless of success or failure.
# If the checkpoint write itself fails, _write_checkpoint logs to stdout
# and does NOT raise (Requirement 8.5).
_write_checkpoint(
    batch_id=_batch_id,
    start_time=_run_start,
    record_count=_record_count,
    status=_status,
    error_message=_error_msg,
)

# COMMAND ----------
# MAGIC %md ## 15. Run summary

# COMMAND ----------

print("=" * 65)
print("03_silver_to_gold run complete")
print(f"  batch_id      : {_batch_id}")
print(f"  status        : {_status}")
print(f"  total records : {_record_count if _record_count is not None else 'N/A'}")
if _error_msg:
    print(f"  error         : {_error_msg}")
print("=" * 65)

# Surface the failure so the Databricks UI marks the job as failed.
if _status == "failed":
    raise RuntimeError(
        f"[03_silver_to_gold] Aggregation failed "
        f"(batch_id={_batch_id!r}): {_error_msg}"
    )
