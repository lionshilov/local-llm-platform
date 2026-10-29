# Chat UI

A ChatGPT-style interface for local models, served by the [gateway](../services/gateway)
at http://127.0.0.1:8000.

- **Live metrics on every reply**: time to first token, decode speed and token counts,
  measured in the browser with the same definitions as [`llm-bench`](../packages/llm-bench).
- **Arena**: one prompt, two backends, answers streamed side by side with a speed verdict.
  "Fair timing" runs them one after another so they don't share the GPU.
- **Thinking mode**: toggles the model's reasoning; the trace streams into a collapsible block.
- **Markdown done properly**: GFM tables, syntax-highlighted code with copy buttons, and
  LaTeX via KaTeX, with a pre-processor that keeps prices like "$1.10" from being
  parsed as formulas.
- **Engine discovery**: the model picker polls `/v1/models` and shows which engines are
  online; start or stop one and the UI follows.
- **Stop and regenerate**: aborting the request closes the upstream connection, so the
  engine stops generating too.
- **Private by default**: conversations live in `localStorage`; no fonts, analytics or
  CDNs are loaded from the internet.

## Development

```bash
npm ci
npm run dev        # http://127.0.0.1:5173, proxies /v1 to the gateway on :8000
npm test           # vitest: SSE parsing, metrics, math pre-processing, markdown rendering
npm run typecheck
npm run build      # ui/dist, served by the gateway
```

Stack: React 19, TypeScript (strict), Vite, Tailwind CSS 4, react-markdown with
remark-gfm/remark-math, rehype-highlight and rehype-katex. Markdown, KaTeX and
highlight.js are lazy-loaded with the first reply, so the initial bundle stays at ~80 kB
gzipped.

| Path | Responsibility |
|---|---|
| `src/lib/api.ts` | Streaming client for `/v1/chat/completions`, timing per chunk |
| `src/lib/sse.ts` | Incremental SSE parser and latency math |
| `src/lib/reply.ts` | One assistant reply: request building, frame-batched updates, stop/error handling |
| `src/lib/math.ts` | LaTeX delimiter normalization and price escaping |
| `src/hooks/useChat.ts` | Conversations, persistence, send/stop/regenerate |
| `src/hooks/useArena.ts` | Two-backend races, parallel or fair timing |
