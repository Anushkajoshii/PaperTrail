.PHONY: help install dev worker test lint format eval eval-smoke deploy destroy rulebook-docs demo

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

deploy: ## Deploy to AWS with Terraform (Part 8; asks before creating anything)
	@echo "Deployment arrives in Part 8. Nothing is created without your approval."

destroy: ## Tear down all AWS resources (Part 8)
	@echo "Teardown arrives in Part 8."

rulebook-docs: ## Regenerate docs/SEBI_RULEBOOK.md from the rules and sources
	uv run python -m papertrail.rulebook.catalog_doc > docs/SEBI_RULEBOOK.md

demo: ## Run a full offline check on a sample (FILE=examples/english_post.txt)
	uv run python -m papertrail.agent.run $(or $(FILE),examples/hinglish_reel.txt)
