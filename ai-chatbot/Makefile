# Makefile — AI Catalog Chatbot
#
# Targets:
#   install        Install Python dependencies into a local venv
#   test           Run pytest test suite
#   lint           Run ruff linter
#   build          Build the Docker image locally
#   deploy         Run the full deploy.sh script
#   secrets-sync   Sync local .env.chatbot to AWS Secrets Manager
#   health         Curl the local health endpoint
#   logs           Tail live ECS service logs from CloudWatch
#   help           Show this message
#
# Usage:
#   make install
#   make test
#   ENV=prod make deploy
#
# Prerequisites:
#   • Python 3.11+ with venv
#   • Docker daemon running (for 'build' and 'deploy')
#   • AWS CLI v2 configured (for 'deploy', 'secrets-sync', 'logs')
#   • jq installed (for secrets parsing in deploy.sh)

SHELL := /usr/bin/env bash

ENV          ?= dev
REGION       ?= us-east-1
VENV         := .venv
PYTHON       := $(VENV)/bin/python
PIP          := $(VENV)/bin/pip
PYTEST       := $(VENV)/bin/pytest
RUFF         := $(VENV)/bin/ruff

SERVICE_NAME := ai-chatbot-$(ENV)
CLUSTER_NAME := multi-business-$(ENV)
LOG_GROUP    := /ecs/ai-chatbot-$(ENV)
PORT         := 8001

.PHONY: install test lint build deploy secrets-sync health logs help permissions

# ---------------------------------------------------------------------------
# help — print available targets
# ---------------------------------------------------------------------------
help: ## Show this help message
	@echo ""
	@echo "AI Catalog Chatbot — Makefile targets"
	@echo "--------------------------------------"
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
	@echo ""

# ---------------------------------------------------------------------------
# permissions — ensure deploy.sh is executable (run once after cloning)
# ---------------------------------------------------------------------------
permissions: ## Make deploy.sh executable
	chmod +x deploy.sh
	@echo "deploy.sh is now executable."

# ---------------------------------------------------------------------------
# install — create venv and install all dependencies
# ---------------------------------------------------------------------------
install: ## Create .venv and install requirements.txt
	@echo "==> Creating virtual environment in $(VENV) …"
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r requirements.txt --quiet
	@echo "==> Dependencies installed."
	@echo "    Activate with: source $(VENV)/bin/activate"

# ---------------------------------------------------------------------------
# test — run the full pytest suite
# ---------------------------------------------------------------------------
test: ## Run pytest (all tests in tests/)
	@echo "==> Running tests …"
	cd "$(shell pwd)" && $(PYTEST) tests/ -v --tb=short

# ---------------------------------------------------------------------------
# lint — run ruff linter
# ---------------------------------------------------------------------------
lint: ## Run ruff linter across all Python files
	@echo "==> Running ruff …"
	$(RUFF) check . --select E,W,F,I --fix

# ---------------------------------------------------------------------------
# build — build the Docker image locally (does not push)
# ---------------------------------------------------------------------------
build: ## Build Docker image locally as ai-chatbot:latest
	@echo "==> Building Docker image …"
	docker build -t ai-chatbot:latest .
	@echo "==> Image built: ai-chatbot:latest"

# ---------------------------------------------------------------------------
# deploy — run the full deployment script
# ---------------------------------------------------------------------------
deploy: permissions ## Deploy to AWS ECS (ENV=dev|prod)
	@echo "==> Running deploy.sh (ENV=$(ENV)) …"
	ENV=$(ENV) AWS_REGION=$(REGION) bash deploy.sh

# ---------------------------------------------------------------------------
# secrets-sync — push local .env.chatbot to AWS Secrets Manager only
# (subset of deploy — useful when you only changed config, not code)
# ---------------------------------------------------------------------------
secrets-sync: ## Sync infrastructure/secrets/.env.chatbot → Secrets Manager
	@echo "==> Syncing chatbot secrets to AWS Secrets Manager …"
	@SECRETS_FILE="../infrastructure/secrets/.env.chatbot"; \
	if [[ ! -f "$$SECRETS_FILE" ]]; then \
	    echo "ERROR: $$SECRETS_FILE not found."; \
	    echo "  cp .env.example ../infrastructure/secrets/.env.chatbot"; \
	    exit 1; \
	fi; \
	SECRET_JSON=$$(python3 -c " \
import json, sys; \
from pathlib import Path; \
vals = {k.strip(): v.strip() for line in Path('$$SECRETS_FILE').read_text().splitlines() \
    if line.strip() and not line.startswith('#') and '=' in line \
    for k, _, v in [line.partition('=')]};  \
keys = [k.split('=')[0].strip() for line in Path('.env.example').read_text().splitlines() \
    if line.strip() and not line.startswith('#') and '=' in line]; \
print(json.dumps({k: vals.get(k,'') for k in keys})) \
"); \
	SECRET_NAME="multi-business/$(ENV)/chatbot"; \
	if aws secretsmanager describe-secret --secret-id "$$SECRET_NAME" --region $(REGION) &>/dev/null; then \
	    aws secretsmanager put-secret-value --secret-id "$$SECRET_NAME" \
	        --secret-string "$$SECRET_JSON" --region $(REGION) > /dev/null; \
	    echo "  Updated: $$SECRET_NAME"; \
	else \
	    aws secretsmanager create-secret --name "$$SECRET_NAME" \
	        --description "AI Catalog Chatbot config for $(ENV)" \
	        --secret-string "$$SECRET_JSON" --region $(REGION) > /dev/null; \
	    echo "  Created: $$SECRET_NAME"; \
	fi

# ---------------------------------------------------------------------------
# health — verify the local dev server is healthy
# ---------------------------------------------------------------------------
health: ## Curl the local /chat/health endpoint
	@echo "==> Checking http://localhost:$(PORT)/chat/health …"
	@curl -sf http://localhost:$(PORT)/chat/health \
	    && echo "" || echo "  ✗ Health check failed (is the server running?)"

# ---------------------------------------------------------------------------
# logs — tail live CloudWatch logs for the ECS service
# ---------------------------------------------------------------------------
logs: ## Tail live ECS service logs from CloudWatch (ENV=dev|prod)
	@echo "==> Tailing logs: $(LOG_GROUP) (Ctrl-C to stop)"
	aws logs tail "$(LOG_GROUP)" \
	    --follow \
	    --format short \
	    --region $(REGION)
