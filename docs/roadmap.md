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
- [ ] Measure gateway overhead with `llm-bench` (target: < 2 ms added TTFT)

## Phase 3: Agent harness

- [ ] Tool-calling loop from scratch: JSON-schema tools, parallel calls, error recovery
- [ ] Structured output via grammar-constrained decoding (llama.cpp JSON schema)
- [ ] Sandboxed tools (filesystem, shell, HTTP) with explicit permissions
- [ ] MCP client support
- [ ] Run OpenCode / Aider against the local gateway and document what works

## Phase 4: Eval harness

- [ ] Task suites: tool-call accuracy, JSON validity, coding with unit tests, RAG faithfulness
- [ ] LLM-as-judge with calibration against human labels
- [ ] Quality vs speed vs memory across models and quantizations
- [ ] Regression gate in CI

## Phase 5: RAG

- [ ] Local embeddings served by llama.cpp (`--embedding`)
- [ ] Vector store (Qdrant or pgvector), hybrid search, reranker
- [ ] End-to-end evaluation with Phase 4

## Phase 6: Deploy and operate

- [ ] Docker Compose: gateway, vector DB, Prometheus, Grafana dashboards
- [ ] SLOs and alerting on TTFT / error rate
- [ ] GPU deployment recipe (vLLM on a cloud GPU) behind the same gateway
