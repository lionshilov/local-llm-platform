# 0001. The OpenAI Chat Completions API is the only contract between components

## Context

The repo runs the same model on llama.cpp, MLX-LM and Ollama, and adds a gateway, a chat
UI, a benchmark tool, an agent harness and evals on top. Each engine also has a native API
(llama.cpp `/completion`, Ollama `/api/chat`, MLX's Python API) with features the others
lack.

## Decision

Every component talks to every other through `POST /v1/chat/completions` (streaming via
SSE) and `GET /v1/models`. Engine-specific behaviour is passed through `extra_body`
fields in configuration, never through engine-specific client code.

## Consequences

- Any engine, the gateway, or a hosted provider can replace any other by changing a URL.
  The benchmark tool measures the gateway with the same code it uses for engines.
- The same surface is offered by vLLM, SGLang, TGI and every major provider, so nothing
  here is Mac-specific beyond the engine choice.
- We give up engine-native features (llama.cpp's slot save/restore, Ollama's model
  management API). Where differences leak through the common API (the thinking switch,
  reasoning field names) the gateway normalizes them; see
  [inference/README.md](../../inference/README.md#things-that-bite-in-production).
