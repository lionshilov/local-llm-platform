# 0005. Enforce latency budgets with admission control and fallback in the gateway

## Context

The benchmark showed Ollama serving Qwen3.5 one request at a time despite
`OLLAMA_NUM_PARALLEL=4`: the fourth concurrent user waited 22 s for a first token, with no
error anywhere. Engines differ in how much concurrency they handle well, and none of them
rejects work it cannot serve in time.

## Decision

The gateway owns the latency budget. Each backend declares `max_concurrency` (what the
engine can do in parallel), `max_queue` and `queue_timeout_s`. Requests beyond that get
`429` with `Retry-After`, or are re-routed to the backend's `fallbacks` (for Ollama,
llama.cpp serving the same GGUF weights). Only failures before the first token are
retried, so a client never receives two partial answers.

## Consequences

- Admitted requests keep a predictable TTFT; overload becomes visible
  (`llm_gateway_requests_total{outcome="rejected"}`, `llm_gateway_queue_depth`,
  `llm_gateway_fallbacks_total`) instead of silent queueing.
- Limits are static and per gateway instance. Several gateway replicas would need a
  shared limiter (Redis) or engine-reported load (llama.cpp's `/slots`,
  `requests_deferred`) to stay correct; both are possible next steps.
- A fallback may answer with a different engine than the client asked for. Responses say
  so (`X-Backend`, `model`), and the UI marks such replies.
