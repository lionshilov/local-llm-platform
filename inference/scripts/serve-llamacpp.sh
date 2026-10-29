#!/usr/bin/env bash
# Serve a GGUF model with llama.cpp's llama-server (Metal on Apple Silicon, CUDA/CPU elsewhere).
# Every setting can be overridden through the environment.
set -euo pipefail

HF_REPO="${LLAMACPP_HF_REPO:-unsloth/Qwen3.5-4B-GGUF}"
HF_FILE="${LLAMACPP_HF_FILE:-Qwen3.5-4B-Q4_K_M.gguf}"
ALIAS="${LLAMACPP_ALIAS:-qwen3.5-4b}"
HOST="${LLAMACPP_HOST:-127.0.0.1}"
PORT="${LLAMACPP_PORT:-8080}"
PARALLEL="${LLAMACPP_PARALLEL:-4}"   # concurrent decode slots (continuous batching)
CTX="${LLAMACPP_CTX:-32768}"         # total KV-cache budget shared by all slots

# Resolves to the local HF cache path; downloads only on the first run.
MODEL_PATH="$(hf download "$HF_REPO" "$HF_FILE" --quiet)"

exec llama-server \
  --model "$MODEL_PATH" \
  --alias "$ALIAS" \
  --host "$HOST" --port "$PORT" \
  --n-gpu-layers 99 \
  --flash-attn on \
  --ctx-size "$CTX" \
  --parallel "$PARALLEL" \
  --metrics \
  "$@"
