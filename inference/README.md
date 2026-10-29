# Inference engines

The same model, **Qwen3.5-4B** at ~4 bits, served four ways on one Mac: two weight formats
(GGUF and MLX), each through its reference server and through Ollama. All of them speak
the OpenAI Chat Completions API, so every other part of this repo (gateway, harness,
evals, benchmarks) can switch engines by changing a URL.

| | [llama.cpp](https://github.com/ggml-org/llama.cpp) | [MLX-LM](https://github.com/ml-explore/mlx-lm) | [Ollama](https://github.com/ollama/ollama) |
|---|---|---|---|
| **What it is** | C/C++ inference engine (ggml) | Apple's MLX array framework + LLM tooling | Go server + model registry; delegates to a llama.cpp-based or an MLX runner |
| **Weights** | GGUF: K-quants, I-quants | MLX safetensors, affine group quantization | GGUF everywhere; safetensors (NVFP4, MXFP8, bf16) on Apple Silicon |
| **Hardware** | Metal, CUDA, ROCm, Vulkan, CPU | Apple Silicon only | Metal, CUDA, ROCm, CPU |
| **Concurrency** | `--parallel` slots + continuous batching | `--decode-concurrency` batching | `OLLAMA_NUM_PARALLEL` (runner-dependent, see below) |
| **Observability** | Prometheus `/metrics`, `/slots`, per-request `timings` | logs only | logs only |
| **Pick it for** | Control, portability, production on any hardware | Raw speed and fine-tuning on Apple Silicon | Developer experience, model management |

| Configuration | Weights | Size |
|---|---|---|
| llama.cpp · GGUF Q4_K_M | [`unsloth/Qwen3.5-4B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) `Q4_K_M` | 2.7 GB |
| Ollama · GGUF Q4_K_M | `qwen3.5:4b-q4_K_M` (llama.cpp runner) | 3.3 GB (incl. vision projector) |
| MLX-LM · MLX 4-bit | [`mlx-community/Qwen3.5-4B-MLX-4bit`](https://huggingface.co/mlx-community/Qwen3.5-4B-MLX-4bit) | 3.0 GB (incl. vision tower) |
| Ollama · MLX NVFP4 | `qwen3.5:4b-nvfp4` (MLX runner) | 4.0 GB (incl. vision tower) |

## Run it

```bash
brew install llama.cpp ollama
uv tool install mlx-lm
uv tool install huggingface_hub     # provides the `hf` CLI

make fetch-models                   # GGUF + MLX + Ollama weights
make serve-llamacpp                 # :8080
make serve-mlx                      # :8081
make serve-ollama                   # :11434
make probe                          # what's up, which build
make bench                          # isolated benchmark of every engine
```

Every server setting lives in [`scripts/`](scripts) and can be overridden from the
environment, e.g. `LLAMACPP_PARALLEL=8 make serve-llamacpp`.

### Settings kept identical across engines

| Setting | Value | Why |
|---|---|---|
| Parallel requests | 4 | Enables batching without overcommitting 16 GB |
| Context per request | 8k tokens | Fits the long-context scenario (~3.4k tokens) with headroom |
| KV cache precision | f16 | Quantized KV caches trade accuracy for memory; not what we're comparing |
| Flash attention | on for GGUF (ggml) runners | MLX runners use MLX's fused attention kernel |
| Thinking | off | Each engine exposes the switch differently (see below) |
| Sampling | greedy (`temperature: 0`) | Removes sampler differences from the measurement |

## Things that bite in production

Lessons found while building this, each with the fix applied in this repo.

1. **Ollama silently truncates long prompts.** The default context is sized from available
   VRAM: 4k tokens on a 16 GB Mac. A 6k-token RAG prompt loses its beginning with no error.
   Fix: always set `OLLAMA_CONTEXT_LENGTH` (or `num_ctx` per model).

2. **"Disable thinking" is a different knob on every server.** llama.cpp and MLX take
   `chat_template_kwargs: {"enable_thinking": false}` per request; Ollama takes
   `reasoning_effort: "none"`. Reasoning text also comes back under different names:
   `reasoning_content` (llama.cpp) vs `reasoning` (Ollama, MLX). A gateway has to
   normalize this.

3. **Prefix caching makes naive benchmarks lie.** All three engines reuse the KV cache for a
   shared prompt prefix; MLX even reports it (`usage.prompt_tokens_details.cached_tokens`).
   Benchmark the same prompt twice and the second TTFT is mostly a cache hit. llm-bench
   puts a unique nonce at the start of every prompt.

4. **Docker on macOS cannot use the GPU.** Regular containers run in a Linux VM without
   Metal, so inference in Docker on a Mac is CPU-only and several times slower (Docker
   Model Runner and Podman's Vulkan passthrough are workarounds, not the default). The design here:
   inference servers run natively, everything else (gateway, vector DB, observability)
   runs in containers and reaches them via `host.docker.internal`.

5. **Unified memory has a GPU ceiling.** macOS lets the GPU wire only part of RAM, about
   two thirds on a 16 GB machine. Model + KV cache + every other app must fit, which is why
   the benchmark runs one engine at a time. The limit can be raised with
   `sudo sysctl iogpu.wired_limit_mb=<MB>` (resets on reboot).

6. **"4-bit" is not one format.** GGUF `Q4_K_M` mixes 4- and 6-bit blocks (~4.9 bits per
   weight); MLX 4-bit stores an integer scale and bias per group of 64 weights (~4.5 bits);
   NVFP4 stores 4-bit floats with an FP8 scale per block of 16 (~4.5 bits). Equal labels,
   different sizes and different quality. Compare speed *and* quality before calling one
   engine faster (quality is covered by the eval harness).

7. **mlx_lm.server is a reference server, not a production one.** It warns about this on
   startup. Use it for experiments and put the gateway in front for auth, limits and
   metrics.

8. **The same Ollama tag is a different model on different machines.** On Apple Silicon
   `ollama pull qwen3.5:4b` fetched a 4.0 GB NVFP4 safetensors build that runs on Ollama's
   embedded MLX runner; the registry page lists `qwen3.5:4b` as a 3.3 GB GGUF. The runner
   decides batching behaviour and speed, so a benchmark that just says "Ollama" means little.
   Fix: pin explicit tags (`-q4_K_M`, `-nvfp4`) and check `ollama show <model>` or
   `/api/show` (`details.format`, `quantization_level`, `runner`).

9. **Model defaults leak into your requests.** Ollama models ship sampling defaults
   (here `presence_penalty: 1.5`, `temperature: 1`) applied to every request that doesn't
   override them. llm-bench sets `temperature: 0`; anything else you don't set is the
   model author's choice, not yours.
