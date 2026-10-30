# Eval results

Every directory here is one evaluation session with [`llm-evals`](../../packages/evals):

```
evals/<timestamp>/
├── README.md            # combined report: accuracy, paired tests, sub-checks, failures
├── <ts>-<tag>.json      # raw data: every prompt, reply (incl. reasoning), verdict, tokens
└── <ts>-<tag>.md        # per-run report
```

Re-render, merge or re-score (scorer changes need no model calls) with:

```bash
uv run llm-evals report benchmarks/evals/<timestamp>/*.json
uv run llm-evals rescore benchmarks/evals/<timestamp>/*.json
```

See the [methodology](../../packages/evals/README.md#methodology) for how items are scored
and how to read the confidence intervals.
