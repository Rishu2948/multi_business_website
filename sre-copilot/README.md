# SRE Copilot Agent

An AI-powered Site Reliability Engineering assistant for the multi-business website project. It ingests application logs from Amazon CloudWatch, processes them through a Bronze → Silver → Gold Delta Lake pipeline on Databricks Community Edition, and exposes an AWS Bedrock Agent (Claude 3.5 Sonnet) through a React web chat UI.

---

## Architecture Overview

```
CloudWatch Logs
      │ (boto3)
      ▼
Databricks Community Edition (notebooks)
  ├── bronze.app_logs        ← 00_cw_export.py (2-hour rolling window)
  ├── silver.logs            ← 02_bronze_to_silver.py (PII redact, parse, dedupe)
  ├── gold.error_summaries   ┐
  ├── gold.service_health    ├── 03_silver_to_gold.py (hourly aggregations)
  ├── gold.error_patterns    ┘
  └── config.pipeline_checkpoints
      │ (Databricks SQL connector)
      ▼
AWS Lambda: sre-gold-query-tools   ← Bedrock Action Group (5 query tools)
      │
      ▼
AWS Bedrock Agent (Claude 3.5 Sonnet)
      │  Knowledge Base (S3-backed, Titan Embeddings v2)
      ▼
AWS Lambda: sre-chat-handler       ← API Gateway POST /chat
      │
      ▼
React Chat UI (S3 static website)
```

Full architecture diagram in `design.md` (`.kiro/specs/sre-copilot-agent/design.md`).

---

## Quickstart (10 Steps)

### Prerequisites

- AWS CLI configured (`aws configure`) with an IAM user that has CloudFormation, Lambda, S3, Bedrock, and Secrets Manager permissions
- Databricks Community Edition account (free at https://community.cloud.databricks.com)
- Node.js 18+ (for UI build)
- Python 3.12 (for Lambda packaging)
- `make` available

### Step 1 — Clone / enter the directory

```bash
cd sre-copilot/
```

### Step 2 — Set up your Databricks workspace

1. Log in to https://community.cloud.databricks.com
2. Go to **Compute** → create a new cluster (any runtime, single-node)
3. Go to **SQL Warehouses** → start the default warehouse → copy the **HTTP Path** (e.g., `/sql/1.0/warehouses/abc123`)
4. Go to **Settings** → **Developer** → **Access Tokens** → generate a PAT

### Step 3 — Store Databricks credentials in Secrets Manager

```bash
# Deploy the Secrets stack first (creates the placeholder secrets)
aws cloudformation deploy \
  --template-file infra/02-secrets.yaml \
  --stack-name sre-secrets \
  --capabilities CAPABILITY_NAMED_IAM

# Store your Databricks PAT
./scripts/setup_databricks_secrets.sh \
  community.cloud.databricks.com \
  "/sql/1.0/warehouses/YOUR_HTTP_PATH" \
  "YOUR_DATABRICKS_PAT"
```

### Step 4 — Deploy all CloudFormation stacks

```bash
# Option A: full automated deploy
./deploy.sh

# Option B: step-by-step (stacks must deploy in order — each exports values for the next)
aws cloudformation deploy --template-file infra/01-iam-roles.yaml --stack-name sre-iam-roles --capabilities CAPABILITY_NAMED_IAM
aws cloudformation deploy --template-file infra/02-secrets.yaml --stack-name sre-secrets
aws cloudformation deploy --template-file infra/03-s3-buckets.yaml --stack-name sre-s3-buckets
aws cloudformation deploy --template-file infra/04-lambda-tools.yaml --stack-name sre-lambda-tools \
  --parameter-overrides DatabricksHost=community.cloud.databricks.com DatabricksHttpPath=/sql/1.0/warehouses/YOUR_PATH
aws cloudformation deploy --template-file infra/05-lambda-chat.yaml --stack-name sre-lambda-chat
aws cloudformation deploy --template-file infra/06-bedrock-kb.yaml --stack-name sre-bedrock-kb
aws cloudformation deploy --template-file infra/07-bedrock-agent.yaml --stack-name sre-bedrock-agent
```

### Step 5 — Create Delta tables in Databricks

1. Open Databricks workspace → **Workspace** → **Import**
2. Import `notebooks/04_create_tables.py` (select "File" as import type)
3. Attach to your cluster and **Run All**
4. Verify the following databases and tables exist under **Data**:
   - `bronze.app_logs`
   - `silver.logs`
   - `gold.error_summaries`, `gold.service_health`, `gold.error_patterns`
   - `config.pipeline_checkpoints`, `config.dependencies`

### Step 6 — Import and run the pipeline notebooks

Import all notebooks from the `notebooks/` directory into Databricks:

```
notebooks/00_cw_export.py    ← CloudWatch → Bronze (schedule every 2 hours)
notebooks/01_backfill.py     ← 30-day historical backfill (run once)
notebooks/02_bronze_to_silver.py  ← Bronze → Silver (schedule after 00)
notebooks/03_silver_to_gold.py    ← Silver → Gold (schedule after 02)
```

**One-time backfill**: Run `01_backfill.py` manually first to populate historical data.

**Scheduling** (Databricks Community Edition):
- Open each notebook → **Schedule** → set a cron schedule
- Recommended: `00_cw_export` every 2h, `02_bronze_to_silver` 15m after, `03_silver_to_gold` 15m after that

> **Note**: Community Edition does not support Databricks Workflows (paid feature). Use the notebook scheduler in the UI instead.

### Step 7 — Upload runbooks to the Knowledge Base

```bash
# Get the KB bucket name from the stack output
KB_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name sre-s3-buckets \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseBucketName`].OutputValue' \
  --output text)

export KB_BUCKET
./scripts/upload_runbooks.sh

# Trigger KB sync (indexes the runbooks into Bedrock's vector store)
python3 scripts/sync_kb.py
```

### Step 8 — Package and deploy Lambda functions

```bash
make package-lambda   # installs deps into layer/python/, zips both Lambda functions
```

The deploy script handles updating the Lambda functions in AWS — if using `./deploy.sh` this step is included automatically.

### Step 9 — Build and deploy the React Chat UI

```bash
make build-ui   # runs: cd chat-ui && npm ci && npm run build

# Deploy to S3
UI_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name sre-s3-buckets \
  --query 'Stacks[0].Outputs[?OutputKey==`UiBucketName`].OutputValue' \
  --output text)

aws s3 sync chat-ui/dist/ s3://$UI_BUCKET/ --delete
```

Get the website URL:
```bash
aws cloudformation describe-stacks \
  --stack-name sre-s3-buckets \
  --query 'Stacks[0].Outputs[?OutputKey==`UiBucketWebsiteUrl`].OutputValue' \
  --output text
```

### Step 10 — Verify end-to-end

```bash
# Test the Bedrock Agent directly via CLI
python3 scripts/test_agent.py

# Open the chat UI URL from Step 9 in your browser
# Ask: "What is the health of checkout-service?"
# Ask: "Show me error patterns from the last 6 hours"
```

---

## Repository Structure

```
sre-copilot/
├── README.md                          ← This file
├── Makefile                           ← make deploy | build-ui | package-lambda | test-*
├── deploy.sh                          ← Full deploy: all 7 CFN stacks + UI + runbooks
├── requirements.txt                   ← Python deps for local dev + Lambda layers
├── .gitignore
│
├── notebooks/                         ← Databricks Community Edition notebooks
│   ├── 00_cw_export.py                ← CloudWatch Logs → bronze.app_logs
│   ├── 01_backfill.py                 ← 30-day historical backfill (run once)
│   ├── 02_bronze_to_silver.py         ← Bronze → silver.logs (PII redact, parse)
│   ├── 03_silver_to_gold.py           ← silver → gold tables (aggregations)
│   ├── 04_create_tables.py            ← DDL: creates all 7 Delta tables
│   └── tests/
│       └── test_silver_udfs_smoke.py  ← Smoke tests for Silver UDFs
│
├── lambda/
│   ├── sre_gold_query_tools/
│   │   ├── handler.py                 ← Bedrock Action Group router + 5 query fns
│   │   ├── requirements.txt
│   │   └── tests/
│   │       ├── conftest.py            ← Mock fixtures (Secrets Manager, Databricks)
│   │       └── test_handler.py        ← Unit + property-based tests
│   └── sre_chat_handler/
│       ├── handler.py                 ← API Gateway proxy → Bedrock Agent invoke
│       ├── requirements.txt
│       └── tests/
│           └── test_handler.py        ← CORS, validation, success, error path tests
│
├── chat-ui/                           ← React 18 + Vite static web app
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx                    ← ChatPage: ChatWindow + InputBar + ErrorBanner
│       ├── components/
│       │   ├── ChatWindow.jsx         ← Scrollable message history (auto-scroll)
│       │   ├── MessageBubble.jsx      ← Markdown-rendered messages (react-markdown)
│       │   ├── InputBar.jsx           ← Input + submit + inline validation
│       │   └── LoadingIndicator.jsx   ← Animated spinner
│       ├── hooks/
│       │   ├── useSession.js          ← UUID per tab via sessionStorage
│       │   └── useChat.js             ← API state: messages, loading, error
│       ├── utils/
│       │   └── api.js                 ← POST /chat wrapper
│       └── tests/
│           ├── InputBar.test.jsx      ← fast-check property tests (validation)
│           └── useChat.test.js        ← fast-check: error recovery, message cap
│
├── infra/                             ← CloudFormation templates (deploy in order)
│   ├── 01-iam-roles.yaml              ← BedrockAgentRole, LambdaToolsRole, LambdaChatRole
│   ├── 02-secrets.yaml               ← Secrets Manager placeholders
│   ├── 03-s3-buckets.yaml            ← Data lake + KB docs + UI hosting buckets
│   ├── 04-lambda-tools.yaml          ← sre-gold-query-tools Lambda + Databricks layer
│   ├── 05-lambda-chat.yaml           ← sre-chat-handler Lambda + API Gateway
│   ├── 06-bedrock-kb.yaml            ← Bedrock Knowledge Base + S3 data source
│   ├── 07-bedrock-agent.yaml         ← Bedrock Agent + Action Group + alias
│   └── params/
│       ├── dev.json                   ← Dev environment parameter overrides
│       └── prod.json                  ← Prod environment parameter overrides
│
├── runbooks/                          ← Markdown runbooks (uploaded to Bedrock KB)
│   ├── checkout-service-runbook.md   ← connection_refused + timeout triage
│   ├── backend-service-runbook.md    ← auth_failure + circuit_breaker triage
│   └── postmortem-template.md        ← Standard incident postmortem template
│
└── scripts/
    ├── setup_databricks_secrets.sh   ← Store Databricks PAT in Secrets Manager
    ├── upload_runbooks.sh             ← aws s3 sync runbooks/ → KB bucket
    ├── sync_kb.py                     ← Trigger Bedrock KB data source re-sync
    └── test_agent.py                  ← CLI end-to-end agent test
```

---

## Makefile Targets

```bash
make package-lambda   # pip install deps into layer/python/, zip Lambda packages
make build-ui         # cd chat-ui && npm ci && npm run build
make deploy           # ./deploy.sh (full stack deployment)
make test-notebooks   # cd notebooks && python -m pytest tests/
make test-lambda      # cd lambda/sre_gold_query_tools && python -m pytest tests/
make test-ui          # cd chat-ui && npx vitest --run
```

---

## Running Tests

```bash
# Python tests (requires: pip install -r requirements.txt)
make test-notebooks
make test-lambda

# JavaScript tests
make test-ui

# All tests
make test-notebooks && make test-lambda && make test-ui
```

**Property-based tests** use [Hypothesis](https://hypothesis.readthedocs.io/) (Python) and [fast-check](https://fast-check.dev/) (JavaScript) with a minimum of 100 iterations per property. Optional PBT files are marked with `*` in `tasks.md`.

---

## Cost Notes

This project is designed to stay within or near AWS free-tier limits.

| Service | Free Tier | Usage in this project |
|---|---|---|
| AWS Lambda | 1M requests/month, 400K GB-seconds/month | Both functions: 256 MB, invoked on-demand only |
| Amazon S3 | 5 GB storage, 20K GET, 2K PUT | 3 buckets; target < 2 GB total data |
| AWS Bedrock | On-demand (pay-per-token) | No provisioned throughput; 1 call per user message |
| AWS Secrets Manager | 30-day free trial; $0.40/secret/month after | 2 secrets: ~$0.80/month |
| API Gateway (HTTP API) | 1M API calls/month free (12 months) | Single `POST /chat` route |
| CloudFormation | Free | 7 stacks |
| Databricks Community Edition | Free | Single-node, no expiry |

**Estimated monthly cost** after free-tier exhaustion: < $5/month for typical SRE demo usage (< 1000 agent invocations/month).

**Cost guardrails built in**:
- Lambda memory capped at 256 MB
- Query results capped at 12 rows per tool call
- No background polling or automatic refresh
- S3 storage pipeline pauses at 4 GB utilisation (checkpoint warning)
- Bedrock Knowledge Base uses S3-backed vector store (no OpenSearch Serverless — saves ~$700/month)

---

## Databricks Community Edition — Import Instructions

Community Edition does not support Git integration or workspace repos. Import notebooks manually:

1. Download the `.py` files from `sre-copilot/notebooks/` to your local machine
2. In the Databricks UI: **Workspace** → your user folder → **⋮** → **Import**
3. Select **File** as the source type
4. Upload each `.py` file individually
5. After import, open each notebook and attach it to your running cluster

**Notebook execution order**:
```
04_create_tables.py   (first — creates schemas and tables)
01_backfill.py        (second — one-time 30-day historical load)
00_cw_export.py       (scheduled — ongoing CloudWatch ingestion)
02_bronze_to_silver.py (scheduled — after 00_cw_export)
03_silver_to_gold.py  (scheduled — after 02_bronze_to_silver)
```

**Two-part table names**: All notebooks use `bronze.app_logs`, `silver.logs`, `gold.error_summaries` etc. — never three-part Unity Catalog names (`catalog.schema.table`). Community Edition does not support Unity Catalog.

---

## Agent Investigation Protocol

When you ask the SRE Copilot a question like "Why is checkout-service failing?", the agent follows this protocol:

1. `query_service_health(service)` — current health score (25/50/75/100) and status
2. `query_error_summary(service, hours_back=6)` — hourly error counts and anomaly flags
3. `query_error_patterns(service)` — top 10 clustered error signatures
4. `query_historical_trend(service, days_back=7)` — 7-day error rate history
5. Knowledge Base search — relevant runbook sections (only when Gold data is empty)
6. `get_service_dependencies(service)` — upstream/downstream dependency map (for cross-service analysis)

Every response includes a data freshness timestamp (ISO 8601 UTC) indicating when the most recent Gold record was written.

---

## Security Notes

- All credentials flow through AWS Secrets Manager (`sre/databricks-pat`, `sre/cloudwatch-credentials`)
- No credentials are hardcoded in any source file or environment variable
- Lambda cold-start fetches the PAT from Secrets Manager and caches it for the duration of the warm execution context
- IAM roles are least-privilege scoped (see `infra/01-iam-roles.yaml`)
- The Bedrock Agent will never include AWS account IDs, tokens, or passwords in chat responses
- PII is stripped from log messages in the Silver transformation (IPs → `[IP]`, tokens → `[REDACTED]`, etc.)

---

## Troubleshooting

**"Databricks SQL warehouse is starting"** — Community Edition warehouses auto-stop after 10 minutes of inactivity. The first query after idle will trigger a cold start (~2 minutes). The Lambda returns a structured error; retry after the warehouse warms up.

**"No data in Gold tables"** — Run the notebooks manually in order: `04_create_tables` → `01_backfill` → `02_bronze_to_silver` → `03_silver_to_gold`. Check `config.pipeline_checkpoints` for `status='failed'` entries.

**"Bedrock agent returns empty response"** — Verify `AGENT_ID` and `AGENT_ALIAS_ID` env vars are set on the `sre-chat-handler` Lambda. Check the agent is in `PREPARED` state in the Bedrock console.

**"Chat UI CORS error"** — Ensure `CORS_ORIGINS` in the API Gateway (stack `05-lambda-chat.yaml`) matches the S3 website URL exactly. S3 website URLs are `http://` not `https://`.

**"Knowledge Base sync not finding runbooks"** — Run `python3 scripts/sync_kb.py` after uploading runbooks. KB sync can take 1–5 minutes. Check the data source sync status in the Bedrock console.

---

## Related Documentation

- Architecture and design decisions: `.kiro/specs/sre-copilot-agent/design.md`
- Full requirements: `.kiro/specs/sre-copilot-agent/requirements.md`
- Implementation task list: `.kiro/specs/sre-copilot-agent/tasks.md`
- AWS deployment guide for the main project: `AWS_DEPLOYMENT_README.md`
- Main project README: `README.md`
