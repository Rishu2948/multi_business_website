# Makefile — SRE Copilot Agent
#
# Targets:
#   package-lambda   Build the sre-gold-query-tools Lambda deployment package
#   build-ui         Install Node deps and build the React Chat UI
#   deploy           Run the full CloudFormation + post-deploy deploy.sh script
#   test-notebooks   Run Databricks notebook unit tests
#   test-lambda      Run Lambda unit tests
#   test-ui          Run Vitest UI tests
#
# Requirements: 5.2, 9.1
#
# Usage:
#   make package-lambda
#   ENV=prod make deploy
#
# NOTE: Run `chmod +x deploy.sh scripts/*.sh` after cloning to make scripts
#       executable.  This is required on Linux/macOS before running `make deploy`.

SHELL := /usr/bin/env bash

# Directories (relative to the repo root where this Makefile lives)
LAMBDA_TOOLS_DIR  := lambda/sre_gold_query_tools
LAYER_DIR         := $(LAMBDA_TOOLS_DIR)/layer/python
LAMBDA_ZIP        := sre-gold-query-tools.zip

LAMBDA_CHAT_DIR   := lambda/sre_chat_handler

CHAT_UI_DIR       := chat-ui
NOTEBOOKS_DIR     := notebooks

.PHONY: package-lambda build-ui deploy test-notebooks test-lambda test-ui \
        help permissions

# ---------------------------------------------------------------------------
# help — print available targets
# ---------------------------------------------------------------------------
help: ## Show this help message
	@echo ""
	@echo "SRE Copilot Agent — Makefile targets"
	@echo "-------------------------------------"
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""

# ---------------------------------------------------------------------------
# permissions — ensure shell scripts are executable (run once after cloning)
# ---------------------------------------------------------------------------
permissions: ## Make all .sh scripts executable
	chmod +x deploy.sh
	chmod +x scripts/setup_databricks_secrets.sh
	chmod +x scripts/upload_runbooks.sh
	@echo "All scripts are now executable."

# ---------------------------------------------------------------------------
# package-lambda — build the sre-gold-query-tools Lambda zip
#
#   1. pip-install runtime dependencies into the Lambda layer directory
#   2. Zip the handler code + layer directory into sre-gold-query-tools.zip
# ---------------------------------------------------------------------------
package-lambda: ## Build sre-gold-query-tools Lambda package (function + layer .zip)
	@echo "==> Installing Lambda layer dependencies into $(LAYER_DIR) …"
	pip install \
		--requirement $(LAMBDA_TOOLS_DIR)/requirements.txt \
		--target $(LAYER_DIR) \
		--upgrade \
		--quiet

	@echo "==> Zipping Lambda function + layer …"
	@rm -f $(LAMBDA_ZIP)
	@# Zip the handler from the lambda dir so the top-level path is handler.py
	cd $(LAMBDA_TOOLS_DIR) && zip -r "../../$(LAMBDA_ZIP)" handler.py
	@# Append the layer/ tree (contains pip-installed packages)
	cd $(LAMBDA_TOOLS_DIR) && zip -r "../../$(LAMBDA_ZIP)" layer/
	@echo "==> Package written to $(LAMBDA_ZIP)"

# ---------------------------------------------------------------------------
# build-ui — install Node dependencies and produce a production build
# ---------------------------------------------------------------------------
build-ui: ## Install npm deps and build the React Chat UI to chat-ui/dist/
	@echo "==> Building React Chat UI …"
	cd $(CHAT_UI_DIR) && npm ci && npm run build
	@echo "==> UI build complete. Output: $(CHAT_UI_DIR)/dist/"

# ---------------------------------------------------------------------------
# deploy — run the full deployment script
# Honour the ENV variable (default: dev).
# ---------------------------------------------------------------------------
deploy: ## Deploy all CloudFormation stacks and post-deploy steps (ENV=dev|prod)
	@echo "==> Running deploy.sh (ENV=$(ENV)) …"
	ENV=$(or $(ENV),dev) bash deploy.sh

# ---------------------------------------------------------------------------
# test-notebooks — run pytest for Databricks notebook unit tests
# ---------------------------------------------------------------------------
test-notebooks: ## Run pytest for the notebooks/tests/ suite
	@echo "==> Running notebook tests …"
	cd $(NOTEBOOKS_DIR) && python -m pytest tests/ -v

# ---------------------------------------------------------------------------
# test-lambda — run pytest for the sre-gold-query-tools Lambda test suite
# ---------------------------------------------------------------------------
test-lambda: ## Run pytest for lambda/sre_gold_query_tools/tests/
	@echo "==> Running Lambda tool tests …"
	cd $(LAMBDA_TOOLS_DIR) && python -m pytest tests/ -v

# ---------------------------------------------------------------------------
# test-ui — run Vitest for the React Chat UI test suite
# ---------------------------------------------------------------------------
test-ui: ## Run Vitest for the chat-ui test suite
	@echo "==> Running UI tests …"
	cd $(CHAT_UI_DIR) && npx vitest --run
