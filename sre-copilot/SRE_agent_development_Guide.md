# SRE Agentic AI — Development & Demo Guide

> **Goal:** Get the SRE Copilot agent running end-to-end in 4 weeks.  
> **Strategy:** Gold-Primary (ETL first, then agent, then Slack integration).  
> **Demo target:** Slack bot that answers "Why is X failing?" using Gold tables + Bedrock KB.

---

## 1. Prerequisites

### Accounts & Access

| Requirement | What You Need | Who Provides |
|---|---|---|
| AWS Account | Console access + CLI configured | Cloud team |
| AWS Bedrock access | Model access enabled (Claude 3.5 Sonnet, Titan Embed v2) | Request via AWS console |
| Databricks workspace | Workspace URL + admin access | Platform team |
| Splunk API access | REST API token + base URL | Splunk admin |
| Slack workspace | Permission to create Slack App | Workspace admin |
| GitHub/repo access | Push access to this repo | Team lead |

### Local Development Tools

```bash
# Python 3.12+
python --version  # Should be 3.12+

# AWS CLI v2
aws --version
aws configure  # Set up your credentials

# Databricks CLI
pip install databricks-cli
databricks configure --token  # Set workspace URL + PAT

# Terraform (for infrastructure)
brew install terraform  # macOS
terraform --version

# Project dependencies
pip install boto3 databricks-sql-connector requests slack-sdk pyspark
```

### Verify Access

```bash
# Test AWS Bedrock access
aws bedrock list-foundation-models --query "modelSummaries[?contains(modelId, 'claude')]"

# Test Databricks access
databricks workspace list /

# Test Splunk access (replace with your values)
curl -s -H "Authorization: Bearer YOUR_SPLUNK_TOKEN" \
  "https://YOUR_SPLUNK_URL/services/search/jobs/export" \
  -d 'search=search index=app_logs | head 5&output_mode=json&earliest_time=-5m'
```

---

## 2. Development Phases (4-Week Plan)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  WEEK 1: Data Pipeline (Splunk → Bronze → Silver → Gold)               │
│  ══════════════════════════════════════════════════════                  │
│  Day 1-2: Bronze setup + Splunk export                                  │
│  Day 3-4: Silver transformation (parse, PII-redact, categorize)         │
│  Day 5:   Gold aggregation (summaries, patterns, health)                │
│                                                                          │
│  WEEK 2: Agent + Gold Tools                                             │
│  ══════════════════════════════                                          │
│  Day 1-2: Bedrock Agent setup (instructions, model config)              │
│  Day 2-3: Lambda tools (query Gold tables)                              │
│  Day 4:   Bedrock KB setup (upload runbooks, configure)                 │
│  Day 5:   End-to-end test (CLI invoke → agent → Gold → response)       │
│                                                                          │
│  WEEK 3: Slack Integration + Splunk Fallback                            │
│  ══════════════════════════════════════════                              │
│  Day 1-2: Slack App setup + event handler Lambda                        │
│  Day 3:   Splunk fallback tool (emergency only)                         │
│  Day 4-5: Agent instruction tuning + testing                            │
│                                                                          │
│  WEEK 4: Polish + Demo                                                  │
│  ═════════════════════════                                               │
│  Day 1-2: Error handling, fallback chains, edge cases                   │
│  Day 3:   Monitoring + CloudWatch alarms                                │
│  Day 4:   Demo preparation + script                                     │
│  Day 5:   DEMO DAY                                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Week 1: Data Pipeline

### Day 1-2: Bronze Layer Setup

**Goal:** Get raw Splunk data into Delta Lake.

#### Step 1: Create Unity Catalog Structure

```sql
-- Run in Databricks SQL or notebook
CREATE CATALOG IF NOT EXISTS sre_catalog;

CREATE SCHEMA IF NOT EXISTS sre_catalog.bronze;
CREATE SCHEMA IF NOT EXISTS sre_catalog.silver;
CREATE SCHEMA IF NOT EXISTS sre_catalog.gold;
CREATE SCHEMA IF NOT EXISTS sre_catalog.config;
CREATE SCHEMA IF NOT EXISTS sre_catalog.knowledge;
CREATE SCHEMA IF NOT EXISTS sre_catalog.state;

-- Create Bronze table
CREATE TABLE IF NOT EXISTS sre_catalog.bronze.app_logs (
    _raw            STRING,
    _time           TIMESTAMP,
    index_name      STRING,
    source          STRING,
    sourcetype      STRING,
    host            STRING,
    splunk_id       STRING,
    _ingested_at    TIMESTAMP,
    _batch_id       STRING
)
USING DELTA
PARTITIONED BY (date(_time))
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.logRetentionDuration' = 'interval 14 days'
);
```

#### Step 2: Splunk Export Script

Create notebook: `/Repos/sre-platform/pipelines/00_splunk_export`

```python
# 00_splunk_export.py
import requests
import json
import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import lit, current_timestamp
from datetime import datetime, timedelta

spark = SparkSession.builder.getOrCreate()

# Config (from Databricks Secrets)
SPLUNK_TOKEN = dbutils.secrets.get(scope="sre-secrets", key="splunk-api-token")
SPLUNK_URL = dbutils.secrets.get(scope="sre-secrets", key="splunk-base-url")

# Time window: last 2 hours (overlap for safety, dedup later)
earliest = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
latest = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
batch_id = f"hourly-{datetime.utcnow().strftime('%Y%m%d-%H%M')}"

print(f"Exporting: {earliest} to {latest} (batch: {batch_id})")

# Create Splunk search job
search_query = 'search index=app_logs | fields _raw, _time, host, source, sourcetype, index'
job_response = requests.post(
    f"{SPLUNK_URL}/services/search/jobs",
    headers={"Authorization": f"Bearer {SPLUNK_TOKEN}"},
    data={
        "search": search_query,
        "earliest_time": earliest,
        "latest_time": latest,
        "output_mode": "json"
    }
)
job_response.raise_for_status()
job_sid = job_response.json()["sid"]
print(f"Job created: {job_sid}")

# Wait for job completion
while True:
    status_resp = requests.get(
        f"{SPLUNK_URL}/services/search/jobs/{job_sid}",
        headers={"Authorization": f"Bearer {SPLUNK_TOKEN}"},
        params={"output_mode": "json"}
    )
    is_done = status_resp.json()["entry"][0]["content"]["isDone"]
    if is_done:
        break
    time.sleep(5)

# Fetch results (paginated)
all_results = []
offset = 0
page_size = 50000

while True:
    results_resp = requests.get(
        f"{SPLUNK_URL}/services/search/jobs/{job_sid}/results",
        headers={"Authorization": f"Bearer {SPLUNK_TOKEN}"},
        params={"output_mode": "json", "count": page_size, "offset": offset}
    )
    batch = results_resp.json().get("results", [])
    if not batch:
        break
    all_results.extend(batch)
    offset += page_size
    print(f"  Fetched {len(all_results)} records...")

print(f"Total records fetched: {len(all_results)}")

# Convert to DataFrame and write to Bronze
if all_results:
    df = spark.createDataFrame(all_results)
    
    bronze_df = df.select(
        df["_raw"].alias("_raw"),
        df["_time"].cast("timestamp").alias("_time"),
        df["index"].alias("index_name"),
        df["source"].alias("source"),
        df["sourcetype"].alias("sourcetype"),
        df["host"].alias("host"),
        lit(None).alias("splunk_id"),  # Add dedup key if available
        current_timestamp().alias("_ingested_at"),
        lit(batch_id).alias("_batch_id")
    )
    
    bronze_df.write \
        .format("delta") \
        .mode("append") \
        .saveAsTable("sre_catalog.bronze.app_logs")
    
    print(f"Written {bronze_df.count()} records to Bronze")
else:
    print("No records to process")
```

#### Step 3: Initial Backfill (30 days)

```python
# 01_backfill.py — Run once to load 30 days of history
# Same as above but loop through 30 days in 6-hour batches
# See SRE_Splunk_to_Delta_Lakehouse.md Section 5.1 for full code
```

### Day 3-4: Silver Layer

Create notebook: `/Repos/sre-platform/pipelines/02_bronze_to_silver`

```python
# 02_bronze_to_silver.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import StringType, MapType
import re

spark = SparkSession.builder.getOrCreate()

# Read unprocessed Bronze data
# (In production, track last processed batch_id in a checkpoint table)
bronze = spark.read.table("sre_catalog.bronze.app_logs") \
    .filter(col("_ingested_at") >= current_timestamp() - expr("INTERVAL 3 HOURS"))

# ─── PII Redaction UDF ───
@udf(StringType())
def redact_pii(text):
    if not text:
        return text
    text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', text)
    text = re.sub(r'\b\d{12}\b', '[ACCOUNT]', text)
    text = re.sub(r'[Bb]earer\s+\S+', 'Bearer [REDACTED]', text)
    text = re.sub(r'(?:password|token|secret|api[_-]?key)[=:]\S+', '[REDACTED]', text, flags=re.I)
    return text

# ─── Field Extraction UDF ───
@udf(MapType(StringType(), StringType()))
def extract_fields(raw):
    if not raw:
        return {}
    result = {}
    patterns = {
        "service": r'service[=:](\S+)',
        "region": r'region[=:](\S+)',
        "level": r'level[=:](\S+)',
        "error_type": r'(\w+(?:Exception|Error|Timeout))',
        "trace_id": r'[Tt]race[_]?[Ii]d[=:](\S+)',
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, raw)
        if match:
            result[field] = match.group(1)
    return result

# ─── Error Categorization UDF ───
@udf(StringType())
def categorize_error(raw):
    if not raw:
        return "unknown"
    text = raw.lower()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    elif "connection refused" in text or "connection reset" in text:
        return "connection_refused"
    elif "out of memory" in text or "oom" in text:
        return "out_of_memory"
    elif "null" in text or "npe" in text:
        return "null_pointer"
    elif "401" in text or "403" in text or "unauthorized" in text:
        return "auth_failure"
    elif "circuit" in text:
        return "circuit_breaker"
    elif "500" in text:
        return "internal_error"
    return "other"

# ─── Transform ───
silver = bronze \
    .withColumn("fields", extract_fields(col("_raw"))) \
    .withColumn("service", col("fields.service")) \
    .withColumn("region", coalesce(col("fields.region"), lit("us-west-2"))) \
    .withColumn("level", upper(coalesce(col("fields.level"), lit("INFO")))) \
    .withColumn("error_type", col("fields.error_type")) \
    .withColumn("trace_id", col("fields.trace_id")) \
    .withColumn("message", redact_pii(col("_raw"))) \
    .withColumn("error_category", categorize_error(col("_raw"))) \
    .withColumn("log_id", sha2(concat(coalesce(col("service"), lit("")), col("_time"), col("_raw")), 256)) \
    .withColumn("timestamp", col("_time")) \
    .withColumn("host_alias", concat(lit("host-"), (abs(hash(col("host"))) % 100).cast("string"))) \
    .withColumn("_processed_at", current_timestamp()) \
    .filter(col("service").isNotNull()) \
    .select(
        "log_id", "timestamp", "service", "region", "level",
        "message", "error_type", "error_category", "trace_id",
        "host_alias", "_processed_at"
    ) \
    .dropDuplicates(["log_id"])

# Write to Silver
silver.write \
    .format("delta") \
    .mode("append") \
    .partitionBy("region", "service") \
    .saveAsTable("sre_catalog.silver.logs")

print(f"Written {silver.count()} records to Silver")
```

### Day 5: Gold Layer

Create notebook: `/Repos/sre-platform/pipelines/03_silver_to_gold`

```python
# 03_silver_to_gold.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.window import Window

spark = SparkSession.builder.getOrCreate()

# ─── GOLD: Error Summaries (per hour/service/region) ───
silver_errors = spark.read.table("sre_catalog.silver.logs") \
    .filter(col("level") == "ERROR") \
    .filter(col("timestamp") >= current_timestamp() - expr("INTERVAL 3 HOURS"))

# Calculate 7-day baseline per service/region
baseline = spark.read.table("sre_catalog.silver.logs") \
    .filter(col("level") == "ERROR") \
    .filter(col("timestamp").between(
        current_timestamp() - expr("INTERVAL 8 DAYS"),
        current_timestamp() - expr("INTERVAL 1 DAYS")
    )) \
    .groupBy("service", "region") \
    .agg((count("*") / (7 * 24)).alias("avg_errors_per_hour"))

# Current hour aggregation
hourly = silver_errors \
    .withColumn("hour", date_trunc("hour", col("timestamp"))) \
    .groupBy("hour", "service", "region") \
    .agg(
        count("*").alias("total_errors"),
        count(when(col("level") == "WARN", True)).alias("total_warnings"),
        first(col("error_type")).alias("top_error_type"),
        first(col("error_category")).alias("top_category"),
        first(col("message")).alias("sample_message"),
        countDistinct("error_type").alias("distinct_errors")
    )

# Join with baseline
summaries = hourly.join(baseline, ["service", "region"], "left") \
    .withColumn("error_rate_vs_normal",
        when(col("avg_errors_per_hour") > 0, col("total_errors") / col("avg_errors_per_hour"))
        .otherwise(lit(1.0))
    ) \
    .withColumn("is_anomalous", col("error_rate_vs_normal") > 2.0) \
    .withColumn("trend_direction", lit("stable")) \
    .withColumn("nl_summary",
        concat(
            col("service"), lit(": "), col("total_errors").cast("string"), lit(" errors"),
            when(col("error_rate_vs_normal") > 1.5,
                concat(lit(" ("), (col("error_rate_vs_normal") * 100).cast("int").cast("string"), lit("% above normal)"))
            ).otherwise(lit("")),
            lit(", top: "), coalesce(col("top_error_type"), lit("unknown"))
        )
    ) \
    .withColumn("top_error_types", array(
        struct(
            col("top_error_type").alias("error_type"),
            col("top_category").alias("category"),
            col("total_errors").alias("count"),
            lit(100.0).alias("pct"),
            col("sample_message"),
            lit(None).cast("string").alias("upstream")
        )
    ))

# Write to Gold
summaries.select(
    "hour", "service", "region", "total_errors", "total_warnings",
    "error_rate_vs_normal", "is_anomalous", "top_error_types",
    "trend_direction", "nl_summary"
).write \
    .format("delta") \
    .mode("overwrite") \
    .option("replaceWhere", 
        f"hour >= '{(datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:00:00')}'") \
    .saveAsTable("sre_catalog.gold.error_summaries")

# ─── GOLD: Service Health ───
health = summaries \
    .withColumn("overall_health",
        when(col("error_rate_vs_normal") <= 1.0, 100.0)
        .when(col("error_rate_vs_normal") <= 2.0, 75.0)
        .when(col("error_rate_vs_normal") <= 5.0, 50.0)
        .otherwise(25.0)
    ) \
    .withColumn("status",
        when(col("overall_health") >= 80, "healthy")
        .when(col("overall_health") >= 50, "degraded")
        .otherwise("critical")
    ) \
    .select(
        col("hour").alias("timestamp_hour"),
        "service", "region", "overall_health", "status"
    )

health.write \
    .format("delta") \
    .mode("overwrite") \
    .option("replaceWhere",
        f"timestamp_hour >= '{(datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:00:00')}'") \
    .saveAsTable("sre_catalog.gold.service_health")

print("Gold tables updated successfully")
```

---

## 4. Week 2: Agent + Tools

### Day 1-2: Bedrock Agent Setup

```python
# scripts/setup_bedrock_agent.py
import boto3
import json

bedrock_agent = boto3.client('bedrock-agent', region_name='us-west-2')

# Create agent
agent_response = bedrock_agent.create_agent(
    agentName='sre-copilot',
    agentResourceRoleArn='arn:aws:iam::ACCOUNT_ID:role/bedrock-agent-role',
    foundationModel='anthropic.claude-3-5-sonnet-20241022-v2:0',
    instruction="""You are an expert Site Reliability Engineer AI assistant.

## Data Strategy (IMPORTANT)
You have access to pre-analyzed Gold tables that contain hourly error summaries,
patterns, and health scores. ALWAYS query Gold tables first.

Only use search_splunk_logs (emergency fallback) when:
1. Gold shows "healthy" but user insists something is wrong
2. Gold data is >1 hour old and user reports issue started minutes ago
3. You need specific raw log message content not in Gold summaries

## Available Tools

### Gold Tables (PRIMARY — use for 90% of queries):
- query_error_summary: Hourly error summaries with baseline comparison
- query_error_patterns: Clustered error patterns with trend and resolution
- query_service_health: Composite health score (0-100)
- query_historical_trend: Multi-day trend analysis
- get_service_dependencies: Service dependency graph

### Emergency Fallback (use only when Gold contradicts user):
- search_splunk_logs: Live Splunk query (slow, use sparingly)

### Knowledge (context):
- [Bedrock KB]: Runbooks, postmortems, SOPs (queried automatically)
- query_dynamic_knowledge: Recent patterns, agent memory, resolutions

## Investigation Protocol
1. Start with query_service_health (overall status)
2. If degraded/critical: query_error_summary (what's wrong)
3. If errors found: query_error_patterns (clustered view)
4. Check query_dynamic_knowledge (seen recently? known fix?)
5. Check Bedrock KB (runbook for this issue?)
6. ONLY if Gold seems stale/contradicts user: search_splunk_logs

## Rules
- Always disclose data freshness ("Based on data from X minutes ago...")
- State confidence level (low/medium/high) with findings
- Never output AWS account numbers, IPs, tokens, or passwords
- Format responses for Slack (bold, bullets, code blocks)
- If you don't have enough info, say what's missing and suggest next steps""",
    idleSessionTTLInSeconds=1800
)

agent_id = agent_response['agent']['agentId']
print(f"Agent created: {agent_id}")
```

### Day 2-3: Lambda Tools

Create Lambda function `sre-gold-query-tools`:

```python
# lambda/sre_gold_query_tools/handler.py
import json
import os
from databricks import sql as dbsql

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST")
DATABRICKS_HTTP_PATH = os.environ.get("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = None  # Loaded from Secrets Manager at runtime

def get_databricks_token():
    global DATABRICKS_TOKEN
    if not DATABRICKS_TOKEN:
        import boto3
        sm = boto3.client('secretsmanager')
        secret = sm.get_secret_value(SecretId='sre/databricks-pat')
        DATABRICKS_TOKEN = secret['SecretString']
    return DATABRICKS_TOKEN

def get_connection():
    return dbsql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=get_databricks_token()
    )

def handler(event, context):
    """Bedrock Agent Action Group handler — routes to appropriate Gold query."""
    action_group = event.get('actionGroup', '')
    function = event.get('function', '')
    parameters = {p['name']: p['value'] for p in event.get('parameters', [])}
    
    # Route to handler
    handlers = {
        'query_error_summary': handle_error_summary,
        'query_error_patterns': handle_error_patterns,
        'query_service_health': handle_service_health,
        'query_historical_trend': handle_historical_trend,
        'get_service_dependencies': handle_dependencies,
    }
    
    handler_fn = handlers.get(function)
    if not handler_fn:
        return error_response(action_group, function, f"Unknown function: {function}")
    
    try:
        result = handler_fn(parameters)
        return success_response(action_group, function, result)
    except Exception as e:
        return error_response(action_group, function, str(e))


def handle_error_summary(params):
    service = params['service']
    hours_back = int(params.get('hours_back', '6'))
    region = params.get('region')
    
    query = f"""
        SELECT hour, total_errors, error_rate_vs_normal, is_anomalous,
               top_error_types, trend_direction, nl_summary
        FROM sre_catalog.gold.error_summaries
        WHERE service = '{service}'
          AND hour >= current_timestamp() - INTERVAL {hours_back} HOURS
    """
    if region:
        query += f" AND region = '{region}'"
    query += " ORDER BY hour DESC LIMIT 12"
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    cursor.close()
    conn.close()
    
    results = [dict(zip(columns, row)) for row in rows]
    
    anomalous_count = sum(1 for r in results if r.get('is_anomalous'))
    
    return {
        "service": service,
        "period": f"last {hours_back} hours",
        "data_freshness": str(results[0]['hour']) if results else "no data",
        "anomalous_hours": anomalous_count,
        "summaries": results[:6]  # Limit to keep token-efficient
    }


def handle_service_health(params):
    service = params['service']
    region = params.get('region')
    
    query = f"""
        SELECT timestamp_hour, overall_health, status
        FROM sre_catalog.gold.service_health
        WHERE service = '{service}'
        ORDER BY timestamp_hour DESC
        LIMIT 1
    """
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not row:
        return {"service": service, "status": "unknown", "message": "No health data available"}
    
    return {
        "service": service,
        "overall_health": row[1],
        "status": row[2],
        "last_updated": str(row[0])
    }


def handle_error_patterns(params):
    service = params['service']
    query = f"""
        SELECT pattern_id, canonical_message, error_category,
               occurrences_24h, trend_7d, is_new_pattern, known_resolution
        FROM sre_catalog.gold.error_patterns
        WHERE service = '{service}'
        ORDER BY occurrences_24h DESC
        LIMIT 5
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    cursor.close()
    conn.close()
    
    return {"service": service, "patterns": [dict(zip(columns, r)) for r in rows]}


def handle_historical_trend(params):
    service = params['service']
    days_back = int(params.get('days_back', '7'))
    
    query = f"""
        SELECT date(hour) as log_date, SUM(total_errors) as daily_errors,
               SUM(CASE WHEN is_anomalous THEN 1 ELSE 0 END) as anomalous_hours
        FROM sre_catalog.gold.error_summaries
        WHERE service = '{service}'
          AND hour >= current_timestamp() - INTERVAL {days_back} DAYS
        GROUP BY date(hour)
        ORDER BY log_date
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    daily = [{"date": str(r[0]), "errors": r[1], "anomalous_hours": r[2]} for r in rows]
    
    return {"service": service, "period": f"{days_back} days", "daily_counts": daily}


def handle_dependencies(params):
    service = params['service']
    query = f"""
        SELECT target_service, dependency_type, protocol
        FROM sre_catalog.config.dependencies
        WHERE source_service = '{service}'
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return {
        "service": service,
        "depends_on": [{"service": r[0], "type": r[1], "protocol": r[2]} for r in rows]
    }


def success_response(action_group, function, result):
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': action_group,
            'function': function,
            'functionResponse': {
                'responseBody': {
                    'TEXT': {'body': json.dumps(result, default=str)}
                }
            }
        }
    }

def error_response(action_group, function, error_msg):
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': action_group,
            'function': function,
            'functionResponse': {
                'responseBody': {
                    'TEXT': {'body': json.dumps({"error": error_msg})}
                }
            }
        }
    }
```

### Day 4: Bedrock KB Setup

See [SRE_Knowledge_Base_Setup.md](./SRE_Knowledge_Base_Setup.md) Section 2 for full walkthrough.

Quick version:
1. Upload runbooks/postmortems to S3
2. Create OpenSearch Serverless collection
3. Create Knowledge Base with semantic chunking
4. Sync data source
5. Associate with agent

### Day 5: End-to-End Test (CLI)

```python
# scripts/test_agent.py
import boto3

bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name='us-west-2')

response = bedrock_runtime.invoke_agent(
    agentId='YOUR_AGENT_ID',
    agentAliasId='YOUR_ALIAS_ID',
    sessionId='test-session-001',
    inputText='Is checkout-service healthy? What errors is it having?'
)

# Stream response
full_response = ""
for event in response['completion']:
    if 'chunk' in event:
        chunk_text = event['chunk']['bytes'].decode()
        full_response += chunk_text
        print(chunk_text, end="")

print(f"\n\n--- Full response length: {len(full_response)} chars ---")
```

---

## 5. Week 3: Slack + Fallback

### Day 1-2: Slack App Setup

#### Create Slack App

1. Go to https://api.slack.com/apps → "Create New App"
2. Choose "From manifest" and use:

```yaml
display_information:
  name: SRE-Copilot
  description: AI-powered SRE assistant
  background_color: "#1a1a2e"

features:
  bot_user:
    display_name: SRE-Copilot
    always_online: true
  app_home:
    home_tab_enabled: true

oauth_config:
  scopes:
    bot:
      - app_mentions:read
      - chat:write
      - channels:history
      - groups:history

settings:
  event_subscriptions:
    bot_events:
      - app_mention
      - message.channels
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: false
```

3. Install to workspace → Copy Bot OAuth Token
4. Store token in Secrets Manager: `sre/slack-bot-token`
5. Set Event Subscriptions URL to your Lambda function URL (after deploy)

#### Slack Handler Lambda

```python
# lambda/sre_slack_handler/handler.py
import json
import os
import boto3
import hashlib
import hmac
import time

bedrock_runtime = boto3.client('bedrock-agent-runtime')
sm = boto3.client('secretsmanager')

AGENT_ID = os.environ['AGENT_ID']
AGENT_ALIAS_ID = os.environ['AGENT_ALIAS_ID']

def handler(event, context):
    """Handle Slack events and invoke Bedrock Agent."""
    body = json.loads(event.get('body', '{}'))
    
    # Slack URL verification challenge
    if body.get('type') == 'url_verification':
        return {'statusCode': 200, 'body': json.dumps({'challenge': body['challenge']})}
    
    # Verify Slack signature
    if not verify_slack_signature(event):
        return {'statusCode': 401, 'body': 'Invalid signature'}
    
    # Handle event
    slack_event = body.get('event', {})
    if slack_event.get('type') == 'app_mention':
        handle_mention(slack_event)
    
    return {'statusCode': 200, 'body': 'ok'}


def handle_mention(event):
    """Process @SRE-Copilot mention."""
    import requests
    
    text = event['text'].split('>', 1)[-1].strip()  # Remove @mention
    channel = event['channel']
    thread_ts = event.get('thread_ts', event['ts'])
    user = event['user']
    
    slack_token = get_secret('sre/slack-bot-token')
    
    # Acknowledge immediately
    requests.post("https://slack.com/api/chat.postMessage", 
        headers={"Authorization": f"Bearer {slack_token}"},
        json={"channel": channel, "thread_ts": thread_ts, 
              "text": ":mag: Investigating..."})
    
    # Invoke Bedrock Agent
    session_id = f"{channel}-{thread_ts}"
    
    response = bedrock_runtime.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=text
    )
    
    # Collect response
    full_response = ""
    for event_chunk in response['completion']:
        if 'chunk' in event_chunk:
            full_response += event_chunk['chunk']['bytes'].decode()
    
    # Post response to Slack
    requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {slack_token}"},
        json={
            "channel": channel,
            "thread_ts": thread_ts,
            "text": full_response,
            "unfurl_links": False
        })


def verify_slack_signature(event):
    """Verify request is from Slack."""
    signing_secret = get_secret('sre/slack-signing-secret')
    timestamp = event['headers'].get('x-slack-request-timestamp', '')
    signature = event['headers'].get('x-slack-signature', '')
    body = event.get('body', '')
    
    if abs(time.time() - int(timestamp)) > 300:
        return False
    
    sig_basestring = f"v0:{timestamp}:{body}"
    computed = 'v0=' + hmac.new(
        signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed, signature)


def get_secret(name):
    response = sm.get_secret_value(SecretId=name)
    return response['SecretString']
```

---

## 6. Demo Script

### Demo Scenario (5 minutes)

```
1. [30s] Introduction
   "This is our SRE Copilot — an AI agent that investigates production issues
    by querying pre-analyzed telemetry data, runbooks, and historical patterns."

2. [60s] Health Check
   Type in Slack: "@SRE-Copilot Is checkout-service healthy?"
   Expected: Agent queries Gold → returns health score, status, any degradation

3. [90s] Error Investigation
   Type: "@SRE-Copilot Why is checkout-service throwing errors in us-west-2?"
   Expected: Agent queries Gold summaries + patterns → identifies top error,
   compares to baseline, checks for known resolution

4. [60s] Historical Context
   Type: "@SRE-Copilot Has this happened before? What was the fix?"
   Expected: Agent queries Bedrock KB → finds INC-4521 postmortem → suggests resolution

5. [60s] Trend Analysis  
   Type: "@SRE-Copilot Is this getting worse? Show me the trend this week."
   Expected: Agent queries historical Gold data → shows daily error counts + trend direction

6. [30s] Wrap-up
   "The agent answered in 4-6 seconds using pre-analyzed data.
    No engineer had to manually search Splunk, cross-reference deploys,
    or look up past incidents. This is Phase 1 — future phases add
    anomaly detection, auto-remediation, and predictive alerts."
```

### Demo Preparation Checklist

- [ ] Ensure ETL pipeline has been running for at least 24 hours (Gold has data)
- [ ] Verify Gold tables have data for the demo service (`SELECT * FROM gold.error_summaries WHERE service='checkout-service' LIMIT 5`)
- [ ] Upload at least 3-5 runbooks and 2-3 postmortems to S3 + sync KB
- [ ] Test agent end-to-end via CLI before demo
- [ ] Have Slack thread ready, bot installed in demo channel
- [ ] Pre-populate `config.dependencies` table with service graph
- [ ] Have a "backup" — if live demo fails, show recorded terminal session

---

## 7. Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Agent returns generic answers | Gold tables empty / agent not finding data | Check ETL ran, verify Gold has rows for the service |
| Agent always calls Splunk (not Gold-primary) | Agent instructions unclear | Revise instructions to emphasize "Gold FIRST, Splunk ONLY on contradiction" |
| Lambda timeout | Databricks SQL Warehouse cold start | Set SQL Warehouse auto-stop to 30 min, or warm it before demo |
| KB returns irrelevant docs | Poor chunking / wrong docs | Check S3 content, try adjusting chunk size (300-800 tokens) |
| Slack bot doesn't respond | Events API URL wrong / Lambda error | Check CloudWatch logs for the Slack handler Lambda |
| PII in agent response | Silver transform missed pattern | Add regex to Silver PII redaction, also check Bedrock Guardrails config |
| Agent says "no data" | Service name mismatch (case-sensitive) | Standardize service names in Silver transform (lowercase all) |