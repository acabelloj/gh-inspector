.DEFAULT_GOAL := help

.PHONY: help install lint format test build clean lint-commits e2e

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install deps and set up pre-commit hooks
	uv sync --extra dev
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg

lint: ## Run ruff linter
	uv run ruff check .

format: ## Run ruff formatter
	uv run ruff format .

test: ## Run tests
	uv run pytest || [ $$? -eq 5 ]

build: ## Build the package
	uv run hatch build

lint-commits: ## Check all commits since main follow Conventional Commits
	@PATTERN="^(feat|fix|docs|chore|ci|test|refactor|style|build|perf)(\(.+\))?!?: .+"; \
	FAILED=0; \
	git log origin/main..HEAD --no-merges --format="%s" | while read msg; do \
		if ! echo "$$msg" | grep -qE "$$PATTERN"; then \
			echo "FAIL: '$$msg'"; \
			exit 1; \
		else \
			echo "OK:   '$$msg'"; \
		fi; \
	done || FAILED=1; \
	exit $$FAILED

e2e: ## Run end-to-end tests against the acabelloj org
	@echo "Running find-python-version..."
	@output=$$(uv run gh-inspector find-python-version acabelloj); \
	echo "$$output"; \
	echo "$$output" | grep -q "3.14" || (echo "FAIL: expected 3.14 in output" && exit 1)
	@echo "Running find-python-library..."
	@uv run gh-inspector find-python-library acabelloj typer
	@echo "E2E passed."

clean: ## Remove build artifacts
	rm -rf dist/ .ruff_cache/ __pycache__ .pytest_cache
