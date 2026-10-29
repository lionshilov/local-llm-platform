# 0004. Closed-loop load, isolated engines, cache-busting nonces

## Context

LLM serving benchmarks are easy to get wrong in ways that flatter the system:

- repeating one prompt lets prefix caching skip prefill, so TTFT looks tiny;
- running several engines at once on unified memory makes them compete for bandwidth;
- the first request includes model loading and kernel compilation;
- reporting only averages hides tail latency and stalls.

## Decision

- **Closed-loop load**: N virtual users each send the next request when the previous one
  finishes; levels of 1, 2 and 4 users are measured separately.
- **Unique nonce** at the start of every prompt. Verified in engine logs: only the 5-token
  chat-template prefix ever hits the cache.
- **Isolation**: `bench-all.sh` starts one engine, measures it, stops it, then moves on.
- **Warm-up** request before measuring.
- **Greedy decoding**, thinking off, matched slots/context/KV precision across engines.
- **Percentiles**: p50/p95 for TTFT and TPOT, p99 for inter-token gaps; raw per-request
  data committed alongside summaries, with hardware and server build.

## Consequences

- Results are reproducible with one command and comparable across engines.
- Closed-loop load measures capacity at a given concurrency, not behaviour under an
  open-loop arrival rate (Poisson); that is a planned addition for SLO testing.
- Small samples per level (4 to 8 requests) keep a full run near 15 minutes on a laptop,
  so p95 values are indicative. Prefill showed up to ±25% run-to-run variance, decode
  ±4%; the README only draws conclusions from differences well outside that.
