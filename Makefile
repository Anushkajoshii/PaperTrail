.PHONY: help install dev worker openapi test lint format eval eval-smoke plan deploy destroy ledger stats stats-prod rulebook-docs demo

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies and git hooks
	uv sync --all-extras
	uv run pre-commit install

dev: ## Run the API locally with auto-reload (checks run in-process): http://localhost:8000/docs
	uv run uvicorn papertrail.api.main:app --reload --port 8000

worker: ## Run the background worker (use with PAPERTRAIL_QUEUE_MODE=sqlite)
	uv run python -m papertrail.worker

test: ## Run unit tests with coverage
	uv run pytest --cov=papertrail --cov-report=term-missing

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint and formatting
	uv run ruff check --fix .
	uv run ruff format .

eval: ## Full eval with the configured LLM provider; report in evals/reports/
	uv run python -m papertrail.evaluation --split full

eval-smoke: ## 15-claim smoke eval + regression gate (what CI runs)
	uv run python -m papertrail.evaluation --split smoke --baseline evals/baselines/mock-smoke.json

plan: ## Show what a deploy would change in AWS (creates nothing)
	AWS_PROFILE=$(or $(AWS_PROFILE),portfolio) scripts/deploy.sh plan

deploy: ## Build, push and deploy to AWS (Terraform asks you to confirm first)
	AWS_PROFILE=$(or $(AWS_PROFILE),portfolio) scripts/deploy.sh apply

destroy: ## Remove every AWS resource (Terraform asks you to confirm first)
	AWS_PROFILE=$(or $(AWS_PROFILE),portfolio) scripts/deploy.sh destroy

rulebook-docs: ## Regenerate docs/SEBI_RULEBOOK.md from the rules and sources
	uv run python -m papertrail.rulebook.catalog_doc > docs/SEBI_RULEBOOK.md

demo: ## Run a full offline check on a sample (FILE=examples/english_post.txt)
	uv run python -m papertrail.agent.run $(or $(FILE),examples/hinglish_reel.txt)

ledger: ## Re-check open stock calls in the Claim Ledger (what the daily AWS job does)
	uv run python -m papertrail.ledger

stats: ## Speed, cost and reliability of recent local checks
	uv run python -m papertrail.observability.stats

stats-prod: ## Same, for the deployed app (reads DynamoDB; needs aws login)
	AWS_PROFILE=$(or $(AWS_PROFILE),portfolio) PAPERTRAIL_STORE_BACKEND=dynamodb \
	  PAPERTRAIL_DYNAMODB_TABLE=papertrail-prod-checks uv run python -m papertrail.observability.stats

openapi: ## Regenerate docs/openapi.json from the API code
	uv run python scripts/export_openapi.py docs/openapi.json
