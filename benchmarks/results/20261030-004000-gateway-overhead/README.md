# Gateway overhead

What the gateway costs, measured two ways with `llm-bench` on an Apple M2 Pro.

## 1. Instant fake backend: the gateway's own cost

[`benchmarks/tools/instant_backend.py`](../../tools/instant_backend.py) streams 64 tokens
with no model behind it, so every difference between calling it directly and through a
gateway instance ([`configs/gateway-instant.yaml`](../../../configs/gateway-instant.yaml))
is the gateway. 200 requests per level, two runs
([`configs/gateway-overhead-instant.yaml`](../../../configs/gateway-overhead-instant.yaml)).

- **TTFT: +1 ms** at one user (1 → 2 ms p50).
- **Per token: about +7 µs** (decode 109k → 64k tok/s per stream).
- **Capacity: one gateway process relays ~20k tokens/s**, about 250× what the engines on
  this machine produce (77 tok/s at best).
- At 16 concurrent instant streams TTFT p50 grows by 22–27 ms: every chunk is parsed,
  normalized and re-serialized in one Python process. More workers, or passing through
  chunks that need no rewriting, would remove most of it.

| Engine | Model | Server |
|---|---|---|
| instant backend, direct | `instant` | - |
| instant backend, via gateway | `instant` | - |

| Engine | Scenario | Users | TTFT p50 ms | TTFT p95 ms | Decode tok/s/user | TPOT p50 ms | ITL p99 ms | Prefill tok/s | Total tok/s | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| instant backend, direct | relay | 1 | 1 | 1 | 109,513.6 | 0.0 | 0.1 | 52,135 | 35,221.3 | 0/200 |
| instant backend, direct | relay | 1 | 1 | 1 | 108,694.9 | 0.0 | 0.1 | 52,159 | 35,026.7 | 0/200 |
| instant backend, direct | relay | 16 | 14 | 19 | 134,316.3 | 0.0 | 0.0 | 3,460 | 47,517.8 | 0/200 |
| instant backend, direct | relay | 16 | 16 | 18 | 134,191.3 | 0.0 | 0.0 | 3,215 | 48,533.1 | 0/200 |
| instant backend, via gateway | relay | 1 | 2 | 2 | 64,692.8 | 0.0 | 0.1 | 25,380 | 19,442.3 | 0/200 |
| instant backend, via gateway | relay | 1 | 2 | 3 | 63,863.5 | 0.0 | 0.1 | 23,575 | 18,130.5 | 0/200 |
| instant backend, via gateway | relay | 16 | 36 | 37 | 69,337.4 | 0.0 | 0.1 | 1,377 | 27,413.4 | 0/200 |
| instant backend, via gateway | relay | 16 | 43 | 61 | 67,184.0 | 0.0 | 0.1 | 1,150 | 21,658.8 | 0/200 |

## 2. Real engine: direct vs via gateway

The same llama.cpp server, direct and through the gateway, two runs
([`configs/gateway-overhead.yaml`](../../../configs/gateway-overhead.yaml)). TPOT agrees
within 0.7 ms (≤ 3%). TTFT differs by up to 300 ms between two runs of the *same* path, so
on a real engine the gateway's ~1 ms is far inside the noise.

| Engine | Model | Server |
|---|---|---|
| llama.cpp direct | `qwen3.5-4b` | llama.cpp b11960-8642541b2 |
| llama.cpp via gateway | `llamacpp` | - |

| Engine | Scenario | Users | TTFT p50 ms | TTFT p95 ms | Decode tok/s/user | TPOT p50 ms | ITL p99 ms | Prefill tok/s | Total tok/s | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| llama.cpp direct | short | 1 | 399 | 657 | 42.1 | 23.8 | 25.9 | 129 | 33.8 | 0/16 |
| llama.cpp direct | short | 1 | 466 | 662 | 41.9 | 23.9 | 26.6 | 110 | 32.0 | 0/16 |
| llama.cpp direct | short | 4 | 1,224 | 1,280 | 20.5 | 48.8 | 50.2 | 42 | 60.0 | 0/16 |
| llama.cpp direct | short | 4 | 1,786 | 2,062 | 20.5 | 48.8 | 52.0 | 28 | 53.6 | 0/16 |
| llama.cpp via gateway | short | 1 | 307 | 464 | 40.9 | 24.5 | 27.7 | 165 | 34.3 | 0/16 |
| llama.cpp via gateway | short | 1 | 605 | 644 | 41.9 | 23.8 | 26.7 | 83 | 30.2 | 0/16 |
| llama.cpp via gateway | short | 4 | 1,304 | 2,124 | 20.2 | 49.4 | 54.2 | 38 | 57.0 | 0/16 |
| llama.cpp via gateway | short | 4 | 1,880 | 2,133 | 20.4 | 49.1 | 53.8 | 27 | 52.8 | 0/16 |
