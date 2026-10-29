# Benchmark results

Every directory under [`results/`](results) is one `make bench` run:

```
results/<timestamp>/
├── README.md          # combined table for all engines
├── <ts>-<engine>.json # raw data: every request, summaries, hardware, server build
└── <ts>-<engine>.md   # per-engine table
```

Re-render any run, or merge several, with:

```bash
uv run llm-bench report benchmarks/results/<timestamp>/*.json
```

See [`packages/llm-bench`](../packages/llm-bench#metrics) for what each column means and
how it is measured.
