# Chat UI

A ChatGPT-style interface for local models, served by the [gateway](../services/gateway)
at http://127.0.0.1:8000. Three modes:

**Chat**

- **Live metrics while it types**: elapsed time, time to first token, decode tok/s and
  token count update as the reply streams; final numbers stay under every reply, measured
  with the same definitions as [`llm-bench`](../packages/llm-bench).
- **Every engine has an identity**: llama.cpp amber, MLX-LM sky, Ollama emerald, used for
  avatars, the model picker, arena columns and the monitor.
- **Thinking mode** with a collapsible, markdown-rendered reasoning trace.
- **Markdown done properly**: GFM tables, highlighted code with copy buttons, LaTeX via
  KaTeX, with a pre-processor that keeps prices like "$1.10" from turning into formulas.
- Edit a sent message and regenerate from there, regenerate the last reply, stop
  generation (the gateway closes the upstream request, so the engine stops too).
- Search, rename (double-click) and delete chats; export a chat to Markdown with metrics.
- Fallbacks are visible: a reply answered by another backend says "served by …".

**Arena**

- One prompt, two engines, streamed side by side with live TTFT and tok/s per column.
- **Fair timing** (default) runs them one after another so they don't share the GPU.
- Each round ends with comparison bars and speed ratios, and you **vote for the better
  answer**. A scoreboard tallies votes and speed wins per pair, in either column order,
  across sessions.

**Monitor**

- Live dashboard scraped from the gateway's Prometheus `/metrics`: throughput, request
  rate, active streams, TTFT p50/p95 and error ratio per backend, with sparklines.

Also: honest offline state (every backend greys out when the gateway is down, the
composer explains why), keyboard shortcuts (`⌘⇧O` new chat, `Esc` stop, `/` focus),
responsive down to phone width, `prefers-reduced-motion` respected, and nothing loaded
from the internet (fonts are bundled, no analytics, chats stay in `localStorage`).

## Development

```bash
npm ci
npm run dev        # http://127.0.0.1:5173, proxies /v1 and /metrics to the gateway on :8000
npm test           # vitest
npm run typecheck
npm run format     # Prettier with Tailwind class sorting
npm run build      # ui/dist, served by the gateway
```

Stack: React 19, TypeScript (strict), Vite, Tailwind CSS 4, react-markdown with
remark-gfm/remark-math, rehype-highlight and rehype-katex, Inter and JetBrains Mono
bundled via Fontsource. Markdown, KaTeX, highlight.js and the monitor are lazy-loaded, so
the first paint stays small.

| Path                             | Responsibility                                                           |
| -------------------------------- | ------------------------------------------------------------------------ |
| `src/lib/api.ts`                 | Streaming client for `/v1/chat/completions`, timing per chunk            |
| `src/lib/sse.ts`                 | Incremental SSE parser and latency math                                  |
| `src/lib/reply.ts`               | One assistant reply: request building, live stats, frame-batched updates |
| `src/lib/math.ts`                | LaTeX delimiter normalization and price escaping                         |
| `src/lib/engines.ts`             | Engine colours and names                                                 |
| `src/lib/export.ts`              | Markdown export                                                          |
| `src/lib/prometheus.ts`          | Prometheus text parser, rates and histogram quantiles                    |
| `src/hooks/useChat.ts`           | Conversations: send, stop, regenerate, edit, rename, persistence         |
| `src/hooks/useArena.ts`          | Arena rounds, fair timing, votes and scoreboard                          |
| `src/hooks/useModels.ts`         | Gateway status and backend discovery                                     |
| `src/hooks/useGatewayMetrics.ts` | Polling `/metrics` into time series for the monitor                      |
