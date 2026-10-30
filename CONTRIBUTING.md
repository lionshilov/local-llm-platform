# Contributing

Thanks for taking a look! Issues and pull requests are welcome.

## Development setup

Requires [uv](https://docs.astral.sh/uv/) (it installs the right Python automatically).

```bash
make install   # uv sync + pre-commit hooks
make check     # exactly what CI runs: format, lint, strict mypy, tests
```

The unit tests use in-process fake OpenAI servers (`llm_bench.testing.FakeServer` for
streaming, `llm_agent.testing.ScriptedServer` for scripted tool-calling conversations), so
they need no model and the whole suite runs in seconds. CI additionally runs the
benchmark, the eval harness and the agent against a real llama.cpp server with a 0.8B
model, and smoke-tests the Docker Compose stack.

## Conventions

- Python 3.12+, fully typed (`mypy --strict`), formatted and linted with Ruff.
- Every behavior change comes with a test.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `chore:` …).
- Shell scripts must pass `shellcheck`.

## Submitting benchmark results

Results from other hardware are very welcome:

1. Run `make bench` (or `llm-bench run` against your own servers).
2. Commit the generated `benchmarks/results/<timestamp>/` directory.
3. Mention the hardware and any non-default server settings in the PR description.

Result files contain hardware model, OS and server builds, but no hostnames or paths.
