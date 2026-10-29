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
| **Errors** | OpenAI-style error bodies: `404` unknown model, `502` backend unreachable, upstream errors passed through |
| **Discovery** | `GET /v1/models` lists backends with live `available` status, used by the UI |
| **Metrics** | `GET /metrics` for Prometheus: requests by outcome, in-flight, TTFT and TPOT histograms, token counters |
| **UI** | Serves the built chat UI from `ui/dist` at `/` |

## Metrics

| Metric | Type | Labels |
|---|---|---|
| `llm_gateway_requests_total` | counter | `backend`, `outcome` (`ok`, `cancelled`, `upstream_error`, `upstream_unavailable`, `upstream_<status>`) |
| `llm_gateway_in_flight_requests` | gauge | `backend` |
| `llm_gateway_time_to_first_token_seconds` | histogram | `backend` |
| `llm_gateway_time_per_output_token_seconds` | histogram | `backend` |
| `llm_gateway_prompt_tokens_total`, `llm_gateway_output_tokens_total` | counter | `backend` |
