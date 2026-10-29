# 0003. Measure with raw HTTP + SSE instead of an SDK

## Context

Time to first token and inter-token latency are measured in milliseconds. Client
libraries add their own buffering, retries, connection handling and response parsing;
any of these can shift timings or hide failures (for example, an automatic retry turns
one slow request into a fast-looking second attempt).

## Decision

`llm-bench`, the gateway relay and the UI client all speak HTTP directly (httpx in
Python, `fetch` + `ReadableStream` in the browser), parse Server-Sent Events themselves,
and timestamp each chunk as it leaves the socket. Token counts come from the server's
`usage` block (`stream_options.include_usage`), with a chunk-count fallback that is
recorded in the results.

## Consequences

- Timings are explainable down to the line of code that takes them, and the three
  clients use the same definitions (TTFT, TPOT, decode tok/s), so numbers in the UI match
  the benchmark.
- We own a small SSE parser in two languages, covered by unit tests including partial
  lines, CRLF and keep-alive comments.
- No retries by design: a failed request is a data point, not something to paper over.
