# Roadmap

Each phase ships something that runs, is tested in CI, and has numbers behind it.

## Phase 1: Inference and benchmarking ✅

- [x] Serve one model on llama.cpp, MLX-LM and Ollama with matched settings
- [x] `llm-bench`: TTFT, TPOT, ITL p99, prefill speed, throughput under concurrency
- [x] Isolated per-engine benchmark runs with committed, reproducible results
- [x] CI: lint, strict typing, unit tests, end-to-end run against a real llama.cpp server
- [ ] Quantization sweep: Q4 / Q6 / Q8 / bf16 for speed and memory
- [ ] Speculative decoding (draft model) on llama.cpp and MLX
- [ ] Peak memory per engine (Metal allocations, not just RSS)

## Phase 2: Gateway and chat UI

- [x] FastAPI service with OpenAI-compatible `/v1/chat/completions` (streaming passthrough)
- [x] Routing by model name and live backend health in `/v1/models`
- [x] Normalize engine quirks: thinking switch, reasoning field names
- [x] Prometheus metrics: TTFT and TPOT histograms, in-flight requests, outcomes, tokens
- [x] Client disconnect cancels the upstream request
- [x] Chat UI: streaming markdown/code/LaTeX, thinking mode, live per-reply metrics
- [x] Arena: race two backends on one prompt, with fair (sequential) timing
- [x] Fallback to another engine when a backend is down, full or failing
- [x] Admission control: per-backend concurrency limits with a bounded queue (429s, not timeouts)
- [ ] Per-API-key limits and a shared limiter for multiple gateway replicas
- [ ] OpenTelemetry traces
- [x] Measure gateway overhead with `llm-bench`: ~1 ms TTFT and ~7 µs per token against an instant backend

## Phase 3: Agent harness ✅

- [x] Tool-calling loop from scratch: JSON-schema tools, parallel calls, error recovery
- [x] Scoped tools with explicit opt-in (workspace files, Python subprocess, SSRF-guarded HTTP)
- [x] JSONL traces with per-step latency, tokens, cache hits and server timings
- [x] 7/7 realistic multi-step tasks on Qwen3.5-4B
- [ ] Real sandboxing for code execution (container or gVisor)
- [ ] Structured output via grammar-constrained decoding (llama.cpp JSON schema)
- [ ] MCP client support
- [ ] Run OpenCode / Aider against the local gateway and document what works

## Phase 4: Eval harness ✅

- [x] Original suites with programmatic scoring: math, reasoning, JSON (prompted vs constrained), tool calls, instruction following
- [x] Wilson intervals, paired McNemar tests, versioned result files with suite hashes
- [x] Thinking on vs off: no significant gain at ~6× the cost
- [x] Smoke run against a real server in CI
- [ ] Coding with unit tests and RAG faithfulness suites
- [ ] Quantization sweep (Q4_K_M vs Q8_0 vs bf16) and engines side by side
- [ ] LLM-as-judge with calibration against human labels
- [ ] Regression gate in CI

## Phase 5: RAG

- [ ] Local embeddings served by llama.cpp (`--embedding`)
- [ ] Vector store (Qdrant or pgvector), hybrid search, reranker
- [ ] End-to-end evaluation with Phase 4

## Phase 6: Deploy and operate ✅

- [x] Docker Compose: hardened gateway image, Prometheus, provisioned Grafana dashboard
- [x] SLOs and multi-window burn-rate alerts on availability, TTFT and TPOT, unit-tested with promtool
- [x] CI builds the image and smoke-tests the whole stack
- [ ] Vector DB in Compose (with Phase 5)
- [ ] GPU deployment recipe (vLLM on a cloud GPU) behind the same gateway
