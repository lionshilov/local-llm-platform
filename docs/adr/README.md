# Architecture decision records

Short records of decisions that shaped this repo: the context, the choice, and what it
costs. Format: [Michael Nygard's ADRs](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

| # | Decision | Status |
|---|---|---|
| [0001](0001-openai-api-as-the-only-contract.md) | The OpenAI Chat Completions API is the only contract between components | Accepted |
| [0002](0002-inference-native-services-in-containers.md) | Inference runs natively on the host; everything else may run in containers | Accepted |
| [0003](0003-raw-http-for-measurement.md) | Measure with raw HTTP + SSE instead of an SDK | Accepted |
| [0004](0004-benchmark-methodology.md) | Closed-loop load, isolated engines, cache-busting nonces | Accepted |
| [0005](0005-admission-control-at-the-gateway.md) | Enforce latency budgets with admission control and fallback in the gateway | Accepted |
| [0006](0006-ui-served-by-the-gateway.md) | The chat UI is a static SPA served by the gateway | Accepted |
