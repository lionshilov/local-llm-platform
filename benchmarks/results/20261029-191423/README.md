**Hardware:** Apple M2 Pro · 16.0 GB · macOS-27.0.1  
**Date:** 2026-10-29 19:14 UTC · llm-bench 0.1.0

| Engine | Model | Server |
|---|---|---|
| llama.cpp · GGUF Q4_K_M | `qwen3.5-4b` | llama.cpp b11960-8642541b2 |
| Ollama · GGUF Q4_K_M | `qwen3.5:4b-q4_K_M` | ollama 0.40.12 |
| MLX-LM · MLX 4-bit | `mlx-community/Qwen3.5-4B-MLX-4bit` | - |
| Ollama · MLX NVFP4 | `qwen3.5:4b-nvfp4` | ollama 0.40.12 |

| Engine | Scenario | Users | TTFT p50 ms | TTFT p95 ms | Decode tok/s/user | TPOT p50 ms | ITL p99 ms | Prefill tok/s | Total tok/s | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| llama.cpp · GGUF Q4_K_M | chat | 1 | 215 | 255 | 39.7 | 25.2 | 29.9 | 234 | 38.6 | 0/8 |
| llama.cpp · GGUF Q4_K_M | chat | 2 | 414 | 464 | 21.8 | 46.1 | 60.0 | 122 | 41.6 | 0/8 |
| llama.cpp · GGUF Q4_K_M | chat | 4 | 770 | 777 | 20.4 | 48.9 | 51.0 | 66 | 77.3 | 0/8 |
| MLX-LM · MLX 4-bit | chat | 1 | 299 | 341 | 50.7 | 19.7 | 24.5 | 167 | 47.7 | 0/8 |
| MLX-LM · MLX 4-bit | chat | 2 | 522 | 862 | 32.2 | 31.0 | 35.8 | 101 | 60.1 | 0/8 |
| MLX-LM · MLX 4-bit | chat | 4 | 847 | 1,254 | 18.0 | 55.6 | 63.9 | 59 | 67.3 | 0/8 |
| Ollama · GGUF Q4_K_M | chat | 1 | 220 | 232 | 40.1 | 24.9 | 31.5 | 229 | 38.9 | 0/8 |
| Ollama · GGUF Q4_K_M | chat | 2 | 7,216 | 7,369 | 37.5 | 26.7 | 31.6 | 7 | 36.4 | 0/8 |
| Ollama · GGUF Q4_K_M | chat | 4 | 22,090 | 22,423 | 36.0 | 27.7 | 50.5 | 2 | 34.9 | 0/8 |
| Ollama · MLX NVFP4 | chat | 1 | 255 | 298 | 42.8 | 23.4 | 33.8 | 197 | 40.5 | 0/8 |
| Ollama · MLX NVFP4 | chat | 2 | 7,278 | 10,115 | 36.4 | 27.5 | 45.1 | 7 | 33.3 | 0/8 |
| Ollama · MLX NVFP4 | chat | 4 | 19,856 | 20,805 | 39.9 | 25.0 | 39.3 | 3 | 37.8 | 0/8 |
| llama.cpp · GGUF Q4_K_M | long-context | 1 | 7,689 | 8,286 | 40.2 | 24.9 | 34.2 | 444 | 3.7 | 0/4 |
| llama.cpp · GGUF Q4_K_M | long-context | 2 | 15,736 | 16,799 | 17.8 | 60.6 | 722.2 | 217 | 4.3 | 0/4 |
| MLX-LM · MLX 4-bit | long-context | 1 | 9,834 | 9,942 | 52.9 | 18.9 | 22.0 | 345 | 4.2 | 0/4 |
| MLX-LM · MLX 4-bit | long-context | 2 | 15,908 | 20,818 | 13.7 | 135.1 | 4,607.5 | 237 | 4.0 | 0/4 |
| Ollama · GGUF Q4_K_M | long-context | 1 | 9,957 | 10,043 | 39.2 | 25.5 | 32.2 | 343 | 3.3 | 0/4 |
| Ollama · GGUF Q4_K_M | long-context | 2 | 19,769 | 20,257 | 36.9 | 27.1 | 42.1 | 173 | 3.4 | 0/4 |
| Ollama · MLX NVFP4 | long-context | 1 | 9,531 | 10,486 | 43.2 | 23.1 | 25.1 | 357 | 2.7 | 0/4 |
| Ollama · MLX NVFP4 | long-context | 2 | 19,758 | 20,319 | 42.4 | 23.6 | 50.4 | 173 | 2.8 | 0/4 |
