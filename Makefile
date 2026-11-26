.PHONY: help install dev test lint format eval deploy destroy rulebook-docs demo

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies and git hooks
	uv sync --all-extras
	uv run pre-commit install

dev: ## Run the app locally (API added in Part 6)
	@echo "Local API arrives in Part 6. For now: make test"

test: ## Run unit tests with coverage
	uv run pytest --cov=papertrail --cov-report=term-missing

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint and formatting
	uv run ruff check --fix .
	uv run ruff format .

eval: ## Run the evaluation suite (added in Part 5)
	@echo "Eval runner arrives in Part 5."

deploy: ## Deploy to AWS with Terraform (Part 8; asks before creating anything)
	@echo "Deployment arrives in Part 8. Nothing is created without your approval."

destroy: ## Tear down all AWS resources (Part 8)
	@echo "Teardown arrives in Part 8."

rulebook-docs: ## Regenerate docs/SEBI_RULEBOOK.md from the rules and sources
	uv run python -m papertrail.rulebook.catalog_doc > docs/SEBI_RULEBOOK.md

demo: ## Run a full offline check on a sample (FILE=examples/english_post.txt)
	uv run python -m papertrail.agent.run $(or $(FILE),examples/hinglish_reel.txt)
