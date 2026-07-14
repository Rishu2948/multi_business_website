#!/usr/bin/env python3
"""sync_kb.py

Triggers a Bedrock Knowledge Base data source ingestion job so that
documents recently uploaded to the S3 runbooks prefix are indexed and
made available to the SRE Copilot Agent.

Usage:
    python scripts/sync_kb.py

Environment variables (required):
    KB_ID         - Bedrock Knowledge Base ID (exported as KnowledgeBaseId
                    by stack 06-bedrock-kb).
    DS_ID         - Bedrock data source ID (exported as DataSourceId by
                    stack 06-bedrock-kb).
    AWS_REGION    - AWS region (default: us-east-1 if not set).

Requirements: 5.2, 9.1

Behaviour:
    • Calls bedrock-agent:StartIngestionJob with the provided KB and data
      source IDs.
    • Logs the ingestion job ID and status on success.
    • Logs the failure and RAISES on error — never silently swallows
      exceptions (Req 5.2).
"""

import logging
import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


def start_ingestion_job(knowledge_base_id: str, data_source_id: str, region: str) -> dict:
    """Start a Bedrock KB ingestion job and return the job descriptor.

    Raises:
        ClientError: If the Bedrock API call fails.
        BotoCoreError: If the boto3 client cannot be initialised.
    """
    client = boto3.client("bedrock-agent", region_name=region)

    logger.info(
        "Starting ingestion job for Knowledge Base %s / Data Source %s in %s ...",
        knowledge_base_id,
        data_source_id,
        region,
    )

    try:
        response = client.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error(
            "Bedrock StartIngestionJob failed: [%s] %s (knowledgeBaseId=%s, dataSourceId=%s)",
            error_code,
            error_msg,
            knowledge_base_id,
            data_source_id,
        )
        # Re-raise so the caller (and deploy.sh) can detect the failure.
        # We do NOT silently swallow the error (Req 5.2).
        raise
    except BotoCoreError as exc:
        logger.error(
            "boto3 client error when starting ingestion job: %s",
            exc,
        )
        raise

    job = response.get("ingestionJob", {})
    job_id = job.get("ingestionJobId", "<unknown>")
    status = job.get("status", "<unknown>")

    logger.info(
        "Ingestion job started successfully. jobId=%s status=%s",
        job_id,
        status,
    )
    return job


def main() -> None:
    """Entry point: read env vars, trigger the ingestion job."""
    knowledge_base_id = os.environ.get("KB_ID", "").strip()
    data_source_id = os.environ.get("DS_ID", "").strip()
    region = os.environ.get("AWS_REGION", "us-east-1").strip()

    missing: list[str] = []
    if not knowledge_base_id:
        missing.append("KB_ID")
    if not data_source_id:
        missing.append("DS_ID")

    if missing:
        logger.error(
            "Required environment variable(s) not set: %s",
            ", ".join(missing),
        )
        logger.error(
            "Set them from CloudFormation stack outputs: "
            "aws cloudformation describe-stacks --stack-name sre-bedrock-kb "
            "--query 'Stacks[0].Outputs'"
        )
        sys.exit(1)

    # start_ingestion_job raises on error — failure is never swallowed.
    start_ingestion_job(knowledge_base_id, data_source_id, region)


if __name__ == "__main__":
    main()
