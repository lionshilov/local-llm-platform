#!/usr/bin/env bash
# Serve an MLX model with mlx-lm (Apple Silicon only; uses Metal through Apple's MLX framework).
set -euo pipefail

MODEL="${MLX_MODEL:-mlx-community/Qwen3.5-4B-MLX-4bit}"
HOST="${MLX_HOST:-127.0.0.1}"
PORT="${MLX_PORT:-8081}"
PARALLEL="${MLX_PARALLEL:-4}"   # requests batched together during decode / prefill

exec mlx_lm.server \
  --model "$MODEL" \
  --host "$HOST" --port "$PORT" \
  --decode-concurrency "$PARALLEL" \
  --prompt-concurrency "$PARALLEL" \
  --log-level WARNING \
  "$@"
