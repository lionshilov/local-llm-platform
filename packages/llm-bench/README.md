# llm-bench

Load generator and latency profiler for **any OpenAI-compatible inference server**:
llama.cpp, MLX-LM, Ollama, vLLM, SGLang, LM Studio, or a hosted API.

It streams real chat completions, timestamps every SSE chunk at the socket boundary, and
reports the numbers that matter when you serve LLMs to users.

## Metrics

| Metric | What it means | Why it matters |
|---|---|---|
| **TTFT** (p50/p95) | Time from sending the request to the first generated token | Perceived responsiveness; dominated by queueing + prefill |
| **TPOT** (p50/p95) | Average time per output token after the first one | Streaming speed a single user sees |
| **Decode tok/s/user** | `1 / TPOT` | Same as TPOT, in the unit people quote |
| **ITL p99** | 99th percentile gap between streamed chunks | Stalls: e.g. other users' prefills blocking your decode |
| **Prefill tok/s** | `prompt_tokens / TTFT` | Prompt processing speed (RAG, long context, agents) |
| **Total tok/s** | All output tokens / wall time of the level | Server capacity at that concurrency |

Token counts come from the server's `usage` block (`stream_options.include_usage`). If a
server doesn't send it, llm-bench falls back to counting text chunks and records
`token_source: "chunks"` in the result file.

## Methodology

- **Closed-loop load**: `N` virtual users, each sending its next request as soon as the
  previous one finishes. Each concurrency level is measured separately.
- **No prefix-cache cheating**: every prompt starts with a unique nonce, so the server
  can't reuse a cached KV prefix from the previous request.
- **Warm-up first**: the first request loads weights and compiles kernels, so it is never
  measured.
- **Greedy decoding** (`temperature: 0`) on every engine.
- **Reasoning-aware**: tokens streamed as `reasoning_content` / `reasoning` count as output.

## Usage

```bash
llm-bench probe                          # which engines are up, which server build
llm-bench run                            # full matrix from configs/bench.yaml
llm-bench run -e mlx -s chat --requests 4
llm-bench report benchmarks/results/<file>.json --format markdown
```

Each run writes `<timestamp>.json` (raw per-request data + summaries + hardware info) and a
`<timestamp>.md` table next to it.

## Config

```yaml
engines:
  llamacpp:
    label: llama.cpp (GGUF Q4_K_M)
    base_url: http://127.0.0.1:8080/v1
    model: qwen3.5-4b
    api_key_env: OPTIONAL_ENV_VAR_NAME
    extra_body:                        # merged into every request body
      chat_template_kwargs: {enable_thinking: false}

scenarios:
  chat:
    prompt_words: 40                   # synthetic prompt size
    max_tokens: 256
    concurrency: [1, 2, 4]
    requests_per_level: 8              # default: max(4, 2 * concurrency)
```
