# Databricks notebook source
# Community Edition compatible — two-part table names (no Unity Catalog)
# Requirements: 1.5, 1.6, 2.7, 3.1, 3.3, 9.1

# COMMAND ----------
# MAGIC %md
# MAGIC # SRE Copilot — Create Delta Databases and Tables
# MAGIC
# MAGIC Run this notebook once on a fresh Databricks Community Edition cluster to
# MAGIC create all required databases and Delta tables before running the pipeline
# MAGIC notebooks (00_cw_export → 01_backfill → 02_bronze_to_silver → 03_silver_to_gold).

# COMMAND ----------

print("Creating databases: bronze, silver, gold, config")

spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
spark.sql("CREATE DATABASE IF NOT EXISTS silver")
spark.sql("CREATE DATABASE IF NOT EXISTS gold")
spark.sql("CREATE DATABASE IF NOT EXISTS config")

print("Databases created successfully.")

# COMMAND ----------
# MAGIC %md ## Bronze Layer

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS bronze.app_logs (
    _raw            STRING       NOT NULL,
    _time           BIGINT       NOT NULL,
    log_group       STRING       NOT NULL,
    log_stream      STRING       NOT NULL,
    source          STRING,
    host            STRING,
    _ingested_at    BIGINT       NOT NULL,
    _batch_id       STRING       NOT NULL
)
USING DELTA
PARTITIONED BY (date(timestamp(_time / 1000)))
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true',
    'delta.logRetentionDuration'       = 'interval 14 days',
    'delta.deletedFileRetentionDuration' = 'interval 14 days'
)
""")

print("Created bronze.app_logs")

# COMMAND ----------
# MAGIC %md ## Config Tables

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS config.pipeline_checkpoints (
    batch_id        STRING    NOT NULL,
    notebook        STRING    NOT NULL,
    record_count    BIGINT,
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP,
    status          STRING    NOT NULL,
    error_message   STRING
)
USING DELTA
""")

print("Created config.pipeline_checkpoints")

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS config.dependencies (
    source_service  STRING  NOT NULL,
    target_service  STRING  NOT NULL,
    dependency_type STRING,
    protocol        STRING
)
USING DELTA
""")

print("Created config.dependencies")

# COMMAND ----------
# MAGIC %md ## Silver Layer

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS silver.logs (
    log_id          STRING     NOT NULL,
    timestamp       TIMESTAMP  NOT NULL,
    service         STRING     NOT NULL,
    region          STRING     NOT NULL,
    level           STRING,
    message         STRING,
    error_type      STRING,
    error_category  STRING,
    trace_id        STRING,
    host_alias      STRING,
    _processed_at   TIMESTAMP  NOT NULL
)
USING DELTA
PARTITIONED BY (region, service)
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true'
)
""")

print("Created silver.logs")

# COMMAND ----------
# MAGIC %md ## Gold Layer

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS gold.error_summaries (
    hour                    TIMESTAMP  NOT NULL,
    service                 STRING     NOT NULL,
    region                  STRING     NOT NULL,
    total_errors            BIGINT     NOT NULL DEFAULT 0,
    total_warnings          BIGINT     NOT NULL DEFAULT 0,
    error_rate_vs_normal    DOUBLE     NOT NULL DEFAULT 1.0,
    is_anomalous            BOOLEAN    NOT NULL DEFAULT FALSE,
    top_error_types         ARRAY<STRUCT<
                              error_type     STRING,
                              category       STRING,
                              count          BIGINT,
                              pct            DOUBLE,
                              sample_message STRING
                            >>,
    trend_direction         STRING,
    nl_summary              STRING
)
USING DELTA
PARTITIONED BY (date(hour))
""")

print("Created gold.error_summaries")

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS gold.service_health (
    timestamp_hour  TIMESTAMP  NOT NULL,
    service         STRING     NOT NULL,
    region          STRING     NOT NULL,
    overall_health  DOUBLE     NOT NULL,
    status          STRING     NOT NULL
)
USING DELTA
PARTITIONED BY (date(timestamp_hour))
""")

print("Created gold.service_health")

# COMMAND ----------

spark.sql("""
CREATE TABLE IF NOT EXISTS gold.error_patterns (
    pattern_id          STRING     NOT NULL,
    service             STRING     NOT NULL,
    error_type          STRING,
    error_category      STRING     NOT NULL,
    canonical_message   STRING,
    occurrences_24h     BIGINT     NOT NULL DEFAULT 0,
    trend_7d            DOUBLE     NOT NULL DEFAULT 1.0,
    is_new_pattern      BOOLEAN    NOT NULL DEFAULT FALSE,
    known_resolution    STRING,
    last_seen           TIMESTAMP  NOT NULL,
    updated_at          TIMESTAMP  NOT NULL
)
USING DELTA
""")

print("Created gold.error_patterns")

# COMMAND ----------
# MAGIC %md ## Verification

# COMMAND ----------

print("\n=== Table Inventory ===")
for db in ["bronze", "silver", "gold", "config"]:
    tables = [row.tableName for row in spark.sql(f"SHOW TABLES IN {db}").collect()]
    print(f"  {db}: {tables}")

print("\nAll Delta tables created successfully.")
print("You can now run: 01_backfill.py (one-time), then schedule 00_cw_export.py, "
      "02_bronze_to_silver.py, 03_silver_to_gold.py.")
