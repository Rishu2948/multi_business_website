# SRE Copilot — Setup & Deployment Guide

This document covers every manual step required before and after running `deploy.sh`,
explains what is automated vs. what you must do yourself, and provides a full reference
for the environment variables and parameters each component expects.

---

## Table of Contents

1. [Architecture at a Glance](#architecture-at-a-glance)
2. [Prerequisites — What You Need First](#prerequisites)
3. [Manual Steps BEFORE Deployment](#manual-steps-before-deployment)
   - [Step 1: AWS Account Setup](#step-1-aws-account-setup)
   - [Step 2: Enable Bedrock Model Access](#step-2-enable-bedrock-model-access)
   - [Step 3: Set Up Databricks Community Edition](#step-3-set-up-databricks-community-edition)
   - [Step 4: Install Local Tools](#step-4-install-local-tools)
   - [Step 5: Create a Deployment S3 Bucket](#step-5-create-a-deployment-s3-bucket)
   - [Step 6: Build & Upload Lambda Packages](#step-6-build--upload-lambda-packages)
   - [Step 7: Fill In Parameter Files](#step-7-fill-in-parameter-files)
4. [Running the Deployment](#running-the-deployment)
5. [Manual Steps AFTER Deployment](#manual-steps-after-deployment)
   - [Step A: Store Databricks Credentials](#step-a-store-databricks-credentials)
   - [Step B: Import and Run Databricks Notebooks](#step-b-import-and-run-databricks-notebooks)
   - [Step C: Update Stack 5 with Agent IDs](#step-c-update-stack-5-with-agent-ids)
   - [Step D: Verify the End-to-End Flow](#step-d-verify-the-end-to-end-flow)
6. [CloudFormation Stack Reference](#cloudformation-stack-reference)
7. [Environment Variables Reference](#environment-variables-reference)
8. [Cost & Free-Tier Notes](#cost--free-tier-notes)
9. [Teardown](#teardown)
10. [Troubleshooting](#troubleshooting)

---

## Architecture at a Glance

```
CloudWatch Logs
       │  (boto3 — Databricks notebook, scheduled)
       ▼
bronze.app_logs  ──▶  silver.logs  ──▶  gold.error_summaries
                                    ──▶  gold.service_health
                                    ──▶  gold.error_patterns
                                    ──▶  config.dependencies
       │                                        │
       │            (Databricks SQL Connector)  │
       └────────────────────────────────────────┘
                                    │
                      Lambda: sre-gold-query-tools
                                    │
                       Bedrock Agent (Claude 3.5 Sonnet)
                       + Knowledge Base (S3 runbooks)
                                    │
                      Lambda: sre-chat-handler
                      API Gateway POST /chat
                                    │
                       React Chat UI (S3 static)
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| AWS CLI v2 | ≥ 2.15 | Deploy CloudFormation, upload S3, manage secrets |
| Python | 3.12 | Lambda runtimes, notebook tests, sync scripts |
| Node.js | ≥ 20 | React Chat UI build |
| npm | ≥ 10 | Chat UI package management |
| pip | latest | Lambda layer packaging |
| make | any | Makefile targets |
| A Databricks Community Edition account | Free | Notebook compute |
| An AWS account | Pay-as-you-go | All AWS services |

---

## Manual Steps BEFORE Deployment

These steps **cannot be automated** — each requires human interaction with an AWS console,
the Databricks UI, or local tooling that is not safe to run unattended.

---

### Step 1: AWS Account Setup

#### 1a — Configure AWS CLI credentials

```bash
aws configure
# AWS Access Key ID:     <your key>
# AWS Secret Access Key: <your secret>
# Default region:        us-east-1   ← must match AWS_REGION in deploy.sh
# Default output format: json
```

Verify:
```bash
aws sts get-caller-identity
```

You need an IAM user or role with these permissions:
- `cloudformation:*`
- `iam:*` (needed to create roles — CloudFormation uses `CAPABILITY_NAMED_IAM`)
- `lambda:*`
- `s3:*`
- `secretsmanager:*`
- `bedrock:*`
- `apigateway:*`
- `logs:*`
- `s3vectors:*` (new S3 Vectors feature — required for the KB stack)

> **Important:** `s3vectors:*` is a relatively new IAM permission namespace.
> If your account's SCPs or permission boundaries are restrictive, confirm
> `s3vectors:CreateVectorBucket`, `s3vectors:CreateIndex`, and related actions
> are allowed before deploying stack 6.

#### 1b — Note your AWS Account ID

```bash
aws sts get-caller-identity --query Account --output text
```

You will need this when naming the deployment bucket (Step 5).

#### 1c — Confirm your target region supports Bedrock + Claude 3.5 Sonnet

Claude 3.5 Sonnet v2 (`anthropic.claude-3-5-sonnet-20241022-v2:0`) is available in:
- `us-east-1` (N. Virginia) ✅ recommended
- `us-west-2` (Oregon) ✅
- `eu-west-1` (Ireland) ✅

Deploy all stacks and the Databricks workspace **in the same region** to avoid
cross-region data transfer costs.

---

### Step 2: Enable Bedrock Model Access

Claude 3.5 Sonnet and Amazon Titan Embeddings v2 require explicit opt-in in the
Bedrock console before they can be used programmatically.

1. Open the AWS Console → **Amazon Bedrock** → **Model access**
2. Click **Manage model access**
3. Enable both:
   - **Anthropic → Claude 3.5 Sonnet v2** (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
   - **Amazon → Titan Embeddings V2 - Text** (`amazon.titan-embed-text-v2:0`)
4. Submit the request. Access is typically granted within a few minutes.

> This is a **required manual step** — CloudFormation cannot request Bedrock model
> access on your behalf. Deploying stack 6 or 7 before access is granted will fail.

---

### Step 3: Set Up Databricks Community Edition

The data pipeline runs entirely on Databricks Community Edition — the free single-node
tier. You need to collect three values from the workspace UI.

#### 3a — Create a Community Edition account

If you don't have one: https://community.cloud.databricks.com/

#### 3b — Create a SQL Warehouse

1. Log in to your Databricks workspace
2. Go to **SQL** → **SQL Warehouses** → **Create SQL Warehouse**
3. Choose the **Starter** size (smallest available; free tier compatible)
4. Give it a name, e.g., `sre-copilot-warehouse`
5. Start the warehouse and wait until its status shows **Running**

#### 3c — Collect the connection details

From the SQL Warehouse detail page → **Connection Details** tab:

| Value | Where to find it | Example |
|---|---|---|
| **Server hostname** | Connection Details tab | `adb-1234567890123456.7.azuredatabricks.net` |
| **HTTP path** | Connection Details tab | `/sql/1.0/warehouses/abcd1234efgh5678` |

Save both values — you will need them in Step 7 and Step A.

#### 3d — Generate a Personal Access Token (PAT)

1. Click your username (top right) → **Settings** → **Developer** → **Access tokens**
2. Click **Generate new token**
3. Set a description: `sre-copilot-lambda`
4. Set lifetime to at least 90 days (or 0 for no expiry on a dev setup)
5. Copy the token **immediately** — it will not be shown again

> Keep the PAT in a password manager. You will store it in AWS Secrets Manager
> (Step A), never in source code or environment variables.

---

### Step 4: Install Local Tools

#### 4a — Python dependencies (for scripts and local tests)

```bash
cd sre-copilot
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The `requirements.txt` installs: `databricks-sql-connector==3.0.2`, `boto3==1.34.0`,
`hypothesis==6.100.0`, `pytest==7.4.0`, `pyspark==3.5.0`.

#### 4b — Node.js dependencies (for the React UI)

```bash
cd sre-copilot/chat-ui
npm install
```

#### 4c — Make scripts executable

```bash
cd sre-copilot
make permissions
```

This runs `chmod +x` on `deploy.sh`, `scripts/setup_databricks_secrets.sh`, and
`scripts/upload_runbooks.sh`.

---

### Step 5: Create a Deployment S3 Bucket

The Lambda CloudFormation stacks (stacks 4 and 5) pull their function `.zip` files
from an S3 bucket named `sre-copilot-deployments-<AccountId>`. You must create this
bucket **before** deploying those stacks.

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1   # change if deploying to a different region

aws s3 mb "s3://sre-copilot-deployments-${ACCOUNT_ID}" --region "${REGION}"
```

> This bucket is not created by any CloudFormation stack because it must exist
> before CloudFormation can read the Lambda zip files from it.

---

### Step 6: Build & Upload Lambda Packages

#### 6a — Build the tools Lambda layer and zip

```bash
cd sre-copilot
make package-lambda
```

This produces `sre-gold-query-tools.zip` in the `sre-copilot/` directory and
populates `lambda/sre_gold_query_tools/layer/python/` with all pip packages.

#### 6b — Upload both Lambda packages to S3

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ENV=dev   # or prod

# Upload the gold query tools zip (function code)
aws s3 cp lambda/sre_gold_query_tools/handler.py /tmp/handler_tools.py
cd lambda/sre_gold_query_tools
zip /tmp/function-${ENV}.zip handler.py
aws s3 cp /tmp/function-${ENV}.zip \
    "s3://sre-copilot-deployments-${ACCOUNT_ID}/lambda/sre_gold_query_tools/function-${ENV}.zip"

# Upload the layer zip
cd layer
zip -r /tmp/layer-${ENV}.zip python/
aws s3 cp /tmp/layer-${ENV}.zip \
    "s3://sre-copilot-deployments-${ACCOUNT_ID}/lambda/sre_gold_query_tools/layer-${ENV}.zip"

cd ../../../..

# Upload the chat handler zip
cd lambda/sre_chat_handler
zip /tmp/chat-function-${ENV}.zip handler.py
aws s3 cp /tmp/chat-function-${ENV}.zip \
    "s3://sre-copilot-deployments-${ACCOUNT_ID}/lambda/sre_chat_handler/function-${ENV}.zip"

cd ../..
```

> Stacks 4 (`sre-lambda-tools`) and 5 (`sre-lambda-chat`) reference these exact
> S3 keys. If the files are not present when those stacks deploy, the stack will fail
> with `InvalidArgument: Could not unzip uploaded file`.

---

### Step 7: Fill In Parameter Files

Each CloudFormation stack that has required parameters must be supplied values
that the automated deploy script cannot derive on its own.

Open `infra/params/dev.json` (or `prod.json` for production) and add the
Databricks parameters that stacks 4 and 5 expect. The current files only contain
`EnvironmentName` and the three override ARNs — you need to extend them:

```json
[
  { "ParameterKey": "EnvironmentName",              "ParameterValue": "dev" },
  { "ParameterKey": "BedrockAgentRoleArnOverride",  "ParameterValue": "" },
  { "ParameterKey": "GoldQueryToolsFunctionArnOverride", "ParameterValue": "" },
  { "ParameterKey": "KnowledgeBaseIdOverride",      "ParameterValue": "" },
  { "ParameterKey": "DatabricksHost",               "ParameterValue": "YOUR_WORKSPACE_HOSTNAME" },
  { "ParameterKey": "DatabricksHttpPath",           "ParameterValue": "/sql/1.0/warehouses/YOUR_WAREHOUSE_ID" },
  { "ParameterKey": "AgentId",                      "ParameterValue": "PLACEHOLDER_FILL_AFTER_STACK7" },
  { "ParameterKey": "AgentAliasId",                 "ParameterValue": "PLACEHOLDER_FILL_AFTER_STACK7" }
]
```

**Notes on the two-phase parameter problem:**

Stack 5 (`sre-lambda-chat`) requires `AgentId` and `AgentAliasId`, which are
outputs of stack 7 (`sre-bedrock-agent`). This creates a circular dependency.

The workaround is a **two-phase deploy**:

- **Phase 1** (first run): deploy stacks 1–7 with placeholder values for `AgentId` and
  `AgentAliasId` in the parameter file. Stack 5 deploys but the chat Lambda has wrong
  env vars — it will fail at runtime until phase 2.
- **Phase 2** (after stack 7 is done): retrieve the real `AgentId` and `AgentAliasId`
  from the stack 7 outputs, update the parameter file, and redeploy stack 5 only:

```bash
# Retrieve the real values
AGENT_ID=$(aws cloudformation describe-stacks \
  --stack-name sre-bedrock-agent \
  --query "Stacks[0].Outputs[?OutputKey=='AgentId'].OutputValue" \
  --output text)

AGENT_ALIAS_ID=$(aws cloudformation describe-stacks \
  --stack-name sre-bedrock-agent \
  --query "Stacks[0].Outputs[?OutputKey=='AgentAliasId'].OutputValue" \
  --output text)

echo "AgentId: $AGENT_ID"
echo "AgentAliasId: $AGENT_ALIAS_ID"
```

Then update `infra/params/dev.json` with the real values and redeploy stack 5:

```bash
aws cloudformation deploy \
  --stack-name sre-lambda-chat \
  --template-file infra/05-lambda-chat.yaml \
  --parameter-overrides file://infra/params/dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

---

## Running the Deployment

Once all pre-deployment steps are complete:

```bash
cd sre-copilot

# Deploy to dev (default)
make deploy

# Or deploy to prod
ENV=prod make deploy

# Or run the script directly
AWS_REGION=us-east-1 ./deploy.sh dev
```

`deploy.sh` executes these phases automatically:

1. Deploys all 7 CloudFormation stacks in order
2. Retrieves stack outputs (bucket names, KB IDs, agent IDs)
3. Uploads runbooks to `s3://sre-copilot-kb-<AccountId>/runbooks/`
4. Triggers a Bedrock Knowledge Base ingestion job (`sync_kb.py`)
5. Builds the React UI (`npm ci && npm run build`) with `VITE_API_URL` injected
6. Syncs `chat-ui/dist/` to `s3://sre-copilot-ui-<AccountId>/`
7. Prints the post-deploy checklist

Estimated time: **15–25 minutes** (Bedrock agent preparation takes the longest).

---

## Manual Steps AFTER Deployment

---

### Step A: Store Databricks Credentials

The deploy script prints this reminder. Run the script now with the values you
collected in Step 3:

```bash
./scripts/setup_databricks_secrets.sh \
    "YOUR_WORKSPACE_HOSTNAME" \
    "/sql/1.0/warehouses/YOUR_WAREHOUSE_ID" \
    "YOUR_DATABRICKS_PAT"
```

This stores:
- `sre/databricks-pat` — the raw PAT string (used by the Lambda at runtime)
- `sre/databricks-config` — `{"host":"...","http_path":"..."}` JSON

The Lambda caches the PAT in a module-level variable on cold start. If you rotate
the PAT, the new value is picked up automatically on the next Lambda cold start.

---

### Step B: Import and Run Databricks Notebooks

The Databricks notebooks cannot be deployed via CloudFormation or the AWS CLI —
they must be imported through the Databricks workspace UI.

#### B1 — Import all notebooks

1. Log in to your Databricks workspace
2. Go to **Workspace** → your user folder (e.g., `/Users/youremail@example.com`)
3. Click the **▾** dropdown → **Import**
4. Import each file from the `notebooks/` directory in this order:

   | File | Purpose | Run when |
   |---|---|---|
   | `04_create_tables.py` | Creates all Delta databases and tables | **Once** — before anything else |
   | `01_backfill.py` | 30-day historical backfill | **Once** — after tables exist |
   | `00_cw_export.py` | Hourly CloudWatch log export | **Scheduled** — every hour |
   | `02_bronze_to_silver.py` | Bronze → Silver transformation | **Scheduled** — after 00 |
   | `03_silver_to_gold.py` | Silver → Gold aggregation | **Scheduled** — after 02 |

#### B2 — Configure AWS credentials in the notebook cluster

The notebooks use `boto3` to call the CloudWatch Logs API. You need to make
your AWS credentials available to the cluster.

**Option A (recommended for CE): Cluster environment variables**

1. Go to **Compute** → click your cluster → **Edit**
2. Under **Advanced options** → **Environment variables**, add:
   ```
   AWS_ACCESS_KEY_ID=<your key>
   AWS_SECRET_ACCESS_KEY=<your secret>
   AWS_DEFAULT_REGION=us-east-1
   ```
3. Click **Confirm** and restart the cluster.

**Option B: Use a cross-account IAM role (requires Enterprise; not CE)**

Not applicable on Community Edition — use Option A.

#### B3 — Configure the CloudWatch log group in the notebooks

Open `notebooks/00_cw_export.py` in Databricks and locate the configuration block
at the top of the notebook. Set:

```python
LOG_GROUP_NAME = "/your/cloudwatch/log/group"   # e.g., "/aws/lambda/checkout-service"
AWS_REGION     = "us-east-1"
```

The same variables appear in `01_backfill.py`.

#### B4 — Run the notebooks in order

1. **Run `04_create_tables.py` first** — this creates the Delta databases
   (`bronze`, `silver`, `gold`, `config`) and all tables. It is idempotent
   (`CREATE TABLE IF NOT EXISTS`) so it is safe to re-run.
2. **Run `01_backfill.py` once** — pulls 30 days of historical logs into Bronze,
   transforms through Silver, and aggregates to Gold. This can take 10–30 minutes
   depending on log volume.
3. **Schedule `00_cw_export.py`** — go to **Workflows** → **Create Job** → add the
   notebook, set schedule to every 1 hour.
4. **Schedule `02_bronze_to_silver.py`** — set schedule to run 10 minutes after
   `00_cw_export` (e.g., every hour at HH:10).
5. **Schedule `03_silver_to_gold.py`** — set schedule to run 20 minutes after
   `00_cw_export` (e.g., every hour at HH:20).

---

### Step C: Update Stack 5 with Agent IDs

As described in Step 7, after stack 7 deploys successfully you need to update the
parameter file and redeploy stack 5 so the chat handler Lambda has the correct
`AGENT_ID` and `AGENT_ALIAS_ID` environment variables.

```bash
# Fetch real values
AGENT_ID=$(aws cloudformation describe-stacks \
  --stack-name sre-bedrock-agent \
  --query "Stacks[0].Outputs[?OutputKey=='AgentId'].OutputValue" \
  --output text)

AGENT_ALIAS_ID=$(aws cloudformation describe-stacks \
  --stack-name sre-bedrock-agent \
  --query "Stacks[0].Outputs[?OutputKey=='AgentAliasId'].OutputValue" \
  --output text)

echo "Update infra/params/dev.json with:"
echo "  AgentId      = $AGENT_ID"
echo "  AgentAliasId = $AGENT_ALIAS_ID"
```

Edit `infra/params/dev.json`, replace the placeholder values, then:

```bash
aws cloudformation deploy \
  --stack-name sre-lambda-chat \
  --template-file infra/05-lambda-chat.yaml \
  --parameter-overrides file://infra/params/dev.json \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --no-fail-on-empty-changeset
```

---

### Step D: Verify the End-to-End Flow

#### D1 — Run the agent CLI test

```bash
AGENT_ID=<from Step C>
AGENT_ALIAS_ID=<from Step C>
AWS_REGION=us-east-1

python scripts/test_agent.py
```

This sends a test question to the live Bedrock Agent and validates a structured
response is returned. If it fails with `ResourceNotFoundException`, the agent is
still preparing — wait 2 minutes and retry.

#### D2 — Open the Chat UI

The UI URL is printed at the end of `deploy.sh`:

```
http://sre-copilot-ui-<AccountId>.s3-website-us-east-1.amazonaws.com
```

Open it in a browser. Type a question like:
> "Is checkout-service healthy right now?"

Expected flow: Loading indicator → Agent invokes `query_service_health` →
returns a Markdown-formatted response with a data freshness timestamp.

---

## CloudFormation Stack Reference

Stacks must be deployed in this order. Each stack imports outputs from earlier stacks.

| # | Stack Name | Template | Deploys | Exports |
|---|---|---|---|---|
| 1 | `sre-iam-roles` | `infra/01-iam-roles.yaml` | BedrockAgentRole, LambdaToolsRole, LambdaChatRole | `BedrockAgentRoleArn`, `LambdaToolsRoleArn`, `LambdaChatRoleArn` |
| 2 | `sre-secrets` | `infra/02-secrets.yaml` | Secrets Manager placeholders | `DatabricksPatSecretArn` |
| 3 | `sre-s3-buckets` | `infra/03-s3-buckets.yaml` | Data lake, KB, and UI buckets | `DataLakeBucketName`, `KnowledgeBaseBucketName`, `KnowledgeBaseBucketArn`, `UiBucketName`, `UiBucketWebsiteUrl` |
| 4 | `sre-lambda-tools` | `infra/04-lambda-tools.yaml` | DatabricksLayer, GoldQueryToolsFunction | `GoldQueryToolsFunctionArn` |
| 5 | `sre-lambda-chat` | `infra/05-lambda-chat.yaml` | ChatHandlerFunction, ChatApi | `ChatApiUrl` |
| 6 | `sre-bedrock-kb` | `infra/06-bedrock-kb.yaml` | S3 Vectors bucket+index, KnowledgeBase, DataSource | `KnowledgeBaseId`, `DataSourceId` |
| 7 | `sre-bedrock-agent` | `infra/07-bedrock-agent.yaml` | SreCopilotAgent, ActionGroup, KbAssociation, AgentAlias | `AgentId`, `AgentAliasId` |

### Required Parameters Summary

| Stack | Parameter | Where to Get It |
|---|---|---|
| 4 | `DatabricksHost` | Databricks → SQL Warehouses → Connection Details |
| 4 | `DatabricksHttpPath` | Databricks → SQL Warehouses → Connection Details |
| 5 | `AgentId` | Stack 7 output (after stack 7 deploys) |
| 5 | `AgentAliasId` | Stack 7 output (after stack 7 deploys) |

---

## Environment Variables Reference

### Lambda: `sre-gold-query-tools`

| Variable | Set by | Value | Notes |
|---|---|---|---|
| `DATABRICKS_HOST` | CloudFormation (stack 4) | `adb-xxxx.cloud.databricks.com` | Non-secret |
| `DATABRICKS_HTTP_PATH` | CloudFormation (stack 4) | `/sql/1.0/warehouses/xxxx` | Non-secret |
| `AWS_REGION` | CloudFormation (injected) | `us-east-1` | Used by boto3 Secrets Manager client |

**At runtime** the handler fetches `sre/databricks-pat` from Secrets Manager and caches
it in a module-level variable. No credentials are stored in environment variables.

### Lambda: `sre-chat-handler`

| Variable | Set by | Value | Notes |
|---|---|---|---|
| `AGENT_ID` | CloudFormation (stack 5) | `XXXXXXXXXX` | Bedrock Agent ID |
| `AGENT_ALIAS_ID` | CloudFormation (stack 5) | `XXXXXXXXXX` | Alias ID for "live" |

### React Chat UI (Vite build-time)

| Variable | Set by | Value | Notes |
|---|---|---|---|
| `VITE_API_URL` | `deploy.sh` (injected at build) | `https://<api-id>.execute-api.<region>.amazonaws.com` | Embedded in the compiled JS bundle |

To change the API URL after initial deployment, rebuild and redeploy the UI:
```bash
VITE_API_URL=https://your-new-url.execute-api.us-east-1.amazonaws.com \
  npm --prefix chat-ui run build
aws s3 sync chat-ui/dist/ s3://sre-copilot-ui-<AccountId>/ --delete
```

### Scripts

| Script | Env Var | Purpose |
|---|---|---|
| `sync_kb.py` | `KB_ID` | Knowledge Base ID (from stack 6 output) |
| `sync_kb.py` | `DS_ID` | Data Source ID (from stack 6 output) |
| `sync_kb.py` | `AWS_REGION` | Region for the boto3 client |
| `test_agent.py` | `AGENT_ID` | Bedrock Agent ID |
| `test_agent.py` | `AGENT_ALIAS_ID` | Bedrock Agent Alias ID |
| `test_agent.py` | `AWS_REGION` | Region for the boto3 client |
| `upload_runbooks.sh` | `KB_BUCKET` | S3 bucket name for runbooks |

---

## Cost & Free-Tier Notes

| Service | Free Tier / Cost |
|---|---|
| **AWS Lambda** | 1M requests + 400K GB-s/month free. Both functions are 256 MB — you get ~1.6M invocations/month before charges. |
| **API Gateway HTTP API** | 1M requests/month free for the first 12 months. |
| **S3** | 5 GB + 20K GET + 2K PUT free per month. The UI, KB, and Delta Lake files should stay well under 2 GB for a demo. |
| **Secrets Manager** | $0.40/secret/month after the first 30 days. Two secrets = ~$0.80/month. |
| **CloudWatch Logs** | 5 GB ingestion free. Lambda and API GW logs have 14-day retention set. |
| **Bedrock (Claude 3.5 Sonnet v2)** | ~$3/$15 per 1M input/output tokens on-demand. A typical agent investigation (4–5 tool calls) costs ~$0.02–0.05. |
| **Bedrock (Titan Embeddings v2)** | $0.00002 per 1K tokens. Embedding a full runbook set (~50 pages) costs < $0.01. |
| **S3 Vectors** | Priced per GB stored and per query. At demo scale (< 1000 vectors) cost is negligible. |
| **Databricks Community Edition** | Free. Single-node; no cluster charges. |

> **Storage budget warning**: The pipeline will write a checkpoint to CloudWatch Logs
> and the Gold aggregation job will log a `stale_source` warning if no new Bronze data
> arrives in > 2 hours. If S3 usage exceeds 4 GB, the Bronze ingestion notebook will
> pause itself (checkpoint `status='paused'`) per Requirement 9.6.

---

## Teardown

To delete all AWS resources and stop incurring charges:

```bash
AWS_REGION=us-east-1

# Delete stacks in reverse order (7 → 1)
for STACK in sre-bedrock-agent sre-bedrock-kb sre-lambda-chat sre-lambda-tools \
             sre-s3-buckets sre-secrets sre-iam-roles; do
  echo "Deleting $STACK ..."
  aws cloudformation delete-stack --stack-name "$STACK" --region "$AWS_REGION"
  aws cloudformation wait stack-delete-complete --stack-name "$STACK" --region "$AWS_REGION"
  echo "$STACK deleted."
done
```

Then empty and delete the S3 buckets (CloudFormation cannot delete non-empty buckets):

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

for BUCKET in \
  "sre-copilot-datalake-${ACCOUNT_ID}" \
  "sre-copilot-kb-${ACCOUNT_ID}" \
  "sre-copilot-ui-${ACCOUNT_ID}" \
  "sre-copilot-deployments-${ACCOUNT_ID}"; do
  echo "Emptying and deleting s3://${BUCKET} ..."
  aws s3 rm "s3://${BUCKET}" --recursive
  aws s3 rb "s3://${BUCKET}"
done
```

Also delete the S3 Vectors bucket (the `sre-bedrock-kb` stack teardown should handle this,
but verify in the console under **S3 → Vector Buckets**).

---

## Troubleshooting

### "The security token included in the request is invalid"
Your AWS CLI credentials have expired. Run `aws configure` again or refresh your session token.

### Stack 4 or 5 fails: "S3 object not found"
The Lambda zip files have not been uploaded to the deployment bucket. Repeat Step 6.

### Stack 6 fails: "s3vectors: action not allowed" or "AccessDenied"
Your IAM user/role is missing `s3vectors:*` permissions. Attach a policy that includes
`s3vectors:CreateVectorBucket`, `s3vectors:CreateIndex`, `s3vectors:PutVectors`, etc.,
or check that your account's SCPs allow the `s3vectors` IAM namespace.

### Stack 7 fails: "Model access denied"
You have not enabled Bedrock model access for Claude 3.5 Sonnet v2 or Titan Embeddings v2.
Go to the Bedrock console → Model access and enable both models (Step 2).

### Chat handler Lambda returns `{"error": "agent_invocation_failed"}`
Check CloudWatch Logs for `/aws/lambda/sre-chat-handler-dev`. Common causes:
- `AGENT_ID` or `AGENT_ALIAS_ID` env vars are still placeholders — complete Step C.
- The Bedrock Agent is still in `PREPARING` state — wait 2 minutes.
- `LambdaChatRole` does not have `bedrock:InvokeAgent` — check stack 1 outputs.

### Gold query Lambda returns `{"error": "secrets_unavailable"}`
The Lambda cannot reach Secrets Manager. Check:
- `LambdaToolsRole` has `secretsmanager:GetSecretValue` for `arn:aws:secretsmanager:*:*:secret:sre/*`
- The secret `sre/databricks-pat` exists (created by stack 2 and populated by Step A)
- The Lambda's VPC configuration (if any) allows outbound HTTPS to Secrets Manager endpoints

### Gold query Lambda returns `{"error": "DatabricksConnectionError"}`
The Databricks SQL Warehouse may be auto-suspended (CE warehouses suspend after 10 minutes
of inactivity). The first request after suspension takes 2–3 minutes to warm up. Retry
the query after the warehouse starts. You can keep it awake by setting a longer auto-suspend
timeout in the Databricks UI.

### Databricks notebook: "No module named boto3"
Install `boto3` on the cluster: **Compute** → your cluster → **Libraries** →
**Install new** → **PyPI** → `boto3==1.34.0`.

### React UI CORS error in the browser console
The `AllowOrigins` in the API Gateway CORS configuration must exactly match the
browser's `Origin` header (including the `http://` prefix). Verify:
```bash
aws cloudformation describe-stacks --stack-name sre-s3-buckets \
  --query "Stacks[0].Outputs[?OutputKey=='UiBucketWebsiteUrl'].OutputValue" \
  --output text
```
The value should be `http://sre-copilot-ui-<AccountId>.s3-website-<region>.amazonaws.com`.
If you are accessing the UI via a custom domain or CloudFront, update the `AllowOrigins`
in stack 5 accordingly.

### `sync_kb.py` fails with `ResourceNotFoundException`
The Knowledge Base or Data Source was not created yet (stack 6 did not complete), or the
`KB_ID` / `DS_ID` environment variables are not set. Run:
```bash
KB_ID=$(aws cloudformation describe-stacks --stack-name sre-bedrock-kb \
  --query "Stacks[0].Outputs[?OutputKey=='KnowledgeBaseId'].OutputValue" --output text)
DS_ID=$(aws cloudformation describe-stacks --stack-name sre-bedrock-kb \
  --query "Stacks[0].Outputs[?OutputKey=='DataSourceId'].OutputValue" --output text)
KB_ID=$KB_ID DS_ID=$DS_ID AWS_REGION=us-east-1 python scripts/sync_kb.py
```
