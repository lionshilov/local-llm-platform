# 0006. The chat UI is a static SPA served by the gateway

## Context

The project needs a usable chat interface for demos and daily use. Options were adopting
an existing UI (Open WebUI, LibreChat), building a server-rendered app, or a static
single-page app.

## Decision

A React + TypeScript SPA built with Vite into static files that the gateway serves at `/`.
It calls the gateway's own `/v1` API from the same origin. In development, Vite proxies
`/v1` to the gateway.

## Consequences

- One process and one port in production, no CORS, no separate web server; the Docker
  image builds the UI in a Node stage and ships only the static files.
- The UI can show what generic UIs don't: per-reply TTFT and decode speed measured like
  the benchmark, which engine actually answered (fallbacks), and an Arena that races two
  engines with an option for sequential "fair timing".
- State lives in the browser (`localStorage`); there are no accounts, sharing or
  server-side history. That fits a single-user local setup and keeps data on the machine.
- Markdown, KaTeX and highlight.js are lazy-loaded so the first paint stays fast
  (~80 kB gzipped).
