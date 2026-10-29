#!/usr/bin/env bash
# Run the Ollama server with settings that match the other engines.
# Pull models separately: `ollama pull qwen3.5:4b` (see fetch-models.sh).
set -euo pipefail

export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-4}"
# Ollama sizes the default context from VRAM (4k on a 16 GB Mac) and silently truncates
# longer prompts. Pin it explicitly; it is allocated per parallel slot.
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-8192}"
export OLLAMA_FLASH_ATTENTION="${OLLAMA_FLASH_ATTENTION:-1}"
export OLLAMA_KV_CACHE_TYPE="${OLLAMA_KV_CACHE_TYPE:-f16}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-30m}"

exec ollama serve "$@"
