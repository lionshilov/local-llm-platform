.DEFAULT_GOAL := help
SCRIPTS := inference/scripts

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## ---- development ----

.PHONY: install
install: ## Install the workspace and git hooks
	uv sync
	uv run pre-commit install

.PHONY: format
format: ## Auto-format and auto-fix lint issues
	uv run ruff format .
	uv run ruff check --fix .

.PHONY: check
check: ## Run everything CI runs (format, lint, types, tests)
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy packages/llm-bench/src
	uv run pytest

.PHONY: test
test: ## Run the test suite
	uv run pytest

## ---- inference ----

.PHONY: fetch-models
fetch-models: ## Download the benchmark model for every engine (~10 GB total)
	$(SCRIPTS)/fetch-models.sh

.PHONY: serve-llamacpp serve-mlx serve-ollama
serve-llamacpp: ## Serve Qwen3.5-4B GGUF with llama.cpp on :8080
	$(SCRIPTS)/serve-llamacpp.sh
serve-mlx: ## Serve Qwen3.5-4B MLX with mlx-lm on :8081
	$(SCRIPTS)/serve-mlx.sh
serve-ollama: ## Run Ollama on :11434
	$(SCRIPTS)/serve-ollama.sh

.PHONY: probe
probe: ## Show which engines are up
	uv run llm-bench probe

.PHONY: bench
bench: ## Benchmark all engines, one at a time, and write a combined report
	$(SCRIPTS)/bench-all.sh
