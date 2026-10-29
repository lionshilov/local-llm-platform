# llm-gateway

One OpenAI-compatible endpoint in front of every local engine. Point any OpenAI SDK, the
bundled chat UI, OpenCode, or `llm-bench` at `http://127.0.0.1:8000/v1` and choose a
backend with the `model` field.

```bash
make gateway          # builds the UI if needed, serves API + UI on :8000
```

```bash
curl http://127.0.0.1:8000/v1/chat/completions -H 'content-type: application/json' -d '{
  "model": "llamacpp",
  "messages": [{"role": "user", "content": "Hello!"}],
  "reasoning_effort": "none",
  "stream": true
}'
```

## What it does

| Concern | Behaviour |
|---|---|
| **Routing** | `model` selects a backend from [`configs/gateway.yaml`](../../configs/gateway.yaml); falls back to `default_backend` |
| **Engine quirks in** | Standard `reasoning_effort` becomes `chat_template_kwargs.enable_thinking` for llama.cpp and MLX, passes through for Ollama |
| **Engine quirks out** | Reasoning text always arrives as `reasoning_content`, whatever the engine calls it; `model` is the backend name |
| **Streaming** | SSE chunks relayed as they arrive (`X-Accel-Buffering: no` for proxies); a client disconnect closes the upstream request so the engine stops generating |
| **Admission control** | Per-backend `max_concurrency` with a bounded `max_queue` and `queue_timeout_s`; overflow gets `429` + `Retry-After` instead of an unbounded wait |
| **Fallback** | Per-backend `fallbacks` list, tried in order when a backend is unreachable, full, or returns 5xx before streaming starts. `X-Backend` header and `model` field say who answered |
| **Errors** | OpenAI-style error bodies: `404` unknown model, `429` at capacity, `502` backend unreachable, upstream 4xx passed through untouched |
| **Discovery** | `GET /v1/models` lists backends with live `available` status, used by the UI |
| **Metrics** | `GET /metrics` for Prometheus: requests by outcome, in-flight, TTFT and TPOT histograms, token counters |
| **UI** | Serves the built chat UI from `ui/dist` at `/` |

## Why admission control and fallback

The benchmark found that Ollama serves Qwen3.5 strictly one request at a time: with four
users, the last one waits 22 s for its first token while the server reports nothing
wrong. A gateway is the right place to enforce a latency budget:

```yaml
ollama-gguf:
  engine: ollama
  base_url: http://127.0.0.1:11434/v1
  model: qwen3.5:4b-q4_K_M
  max_concurrency: 1     # what the engine can actually do in parallel
  fallbacks: [llamacpp]  # same GGUF weights, continuous batching
```

The second concurrent request no longer queues behind the first; it is answered by
llama.cpp immediately, and the response says so (`X-Backend: llamacpp`). With no fallback
configured, it gets a fast `429` with `Retry-After`. Only failures before the first token
are retried, so a client never receives two half-answers.

Slots are released exactly once on every path: normal completion, upstream error,
client disconnect mid-stream, and a disconnect before the first chunk (when the stream
generator never starts, a response background task releases the slot).

## Metrics

| Metric | Type | Labels |
|---|---|---|
| `llm_gateway_requests_total` | counter | `backend`, `outcome` (`ok`, `cancelled`, `rejected`, `upstream_error`, `upstream_unavailable`, `upstream_<status>`) |
| `llm_gateway_in_flight_requests` | gauge | `backend` |
| `llm_gateway_queue_depth` | gauge | `backend` |
| `llm_gateway_fallbacks_total` | counter | `from_backend`, `to_backend` |
| `llm_gateway_time_to_first_token_seconds` | histogram | `backend` |
| `llm_gateway_time_per_output_token_seconds` | histogram | `backend` |
| `llm_gateway_prompt_tokens_total`, `llm_gateway_output_tokens_total` | counter | `backend` |
