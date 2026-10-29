#!/usr/bin/env bash
# Download the same model in the format each engine needs (~3 GB each).
set -euo pipefail

echo "==> GGUF for llama.cpp"
hf download unsloth/Qwen3.5-4B-GGUF Qwen3.5-4B-Q4_K_M.gguf

echo "==> MLX weights for mlx-lm"
hf download mlx-community/Qwen3.5-4B-MLX-4bit

echo "==> Ollama: GGUF (llama.cpp runner) and NVFP4 (MLX runner, Apple Silicon)"
if curl -sf http://127.0.0.1:11434/api/version >/dev/null; then
  ollama pull qwen3.5:4b-q4_K_M
  ollama pull qwen3.5:4b-nvfp4
else
  echo "Ollama is not running; start it with 'make serve-ollama' and re-run this script."
fi
