"""Render results as Markdown (for docs/PRs) or a Rich table (for the terminal)."""

from __future__ import annotations

from collections.abc import Callable

from rich.table import Table

from llm_bench.metrics import LevelSummary
from llm_bench.results import BenchReport, RunRecord


def _fmt(value: float | None, digits: int = 0) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


Column = tuple[str, Callable[[RunRecord], str]]


def _summary(
    getter: Callable[[LevelSummary], float | None], digits: int = 0
) -> Callable[[RunRecord], str]:
    return lambda run: _fmt(getter(run.summary), digits)


COLUMNS: list[Column] = [
    ("Engine", lambda r: r.label or r.engine),
    ("Scenario", lambda r: r.scenario),
    ("Users", lambda r: str(r.concurrency)),
    ("TTFT p50 ms", _summary(lambda s: s.ttft_ms_p50)),
    ("TTFT p95 ms", _summary(lambda s: s.ttft_ms_p95)),
    ("Decode tok/s/user", _summary(lambda s: s.decode_tps_p50, 1)),
    ("TPOT p50 ms", _summary(lambda s: s.tpot_ms_p50, 1)),
    ("ITL p99 ms", _summary(lambda s: s.itl_ms_p99, 1)),
    ("Prefill tok/s", _summary(lambda s: s.prefill_tps_p50)),
    ("Total tok/s", _summary(lambda s: s.output_tps, 1)),
    ("Errors", lambda r: f"{r.summary.errors}/{r.summary.requests}"),
]

_NUMERIC_FROM = 2  # columns from this index on are right-aligned


def _sorted_runs(report: BenchReport) -> list[RunRecord]:
    return sorted(report.runs, key=lambda r: (r.scenario, r.engine, r.concurrency))


def to_markdown(report: BenchReport) -> str:
    system = report.system
    lines = [
        f"**Hardware:** {system.get('cpu')} · {system.get('memory_gb')} GB · {system.get('os')}  ",
        f"**Date:** {report.created_at:%Y-%m-%d %H:%M} UTC · llm-bench {report.tool_version}",
        "",
        "| Engine | Model | Server |",
        "|---|---|---|",
    ]
    for name, info in report.engines.items():
        lines.append(
            f"| {info.get('label') or name} | `{info.get('model')}` | {info.get('server') or '-'} |"
        )
    lines += ["", "| " + " | ".join(title for title, _ in COLUMNS) + " |"]
    lines.append(
        "|" + "|".join("---" if i < _NUMERIC_FROM else "---:" for i in range(len(COLUMNS))) + "|"
    )
    for run in _sorted_runs(report):
        lines.append("| " + " | ".join(render(run) for _, render in COLUMNS) + " |")
    return "\n".join(lines) + "\n"


def to_rich_table(report: BenchReport) -> Table:
    table = Table(title="llm-bench results", header_style="bold cyan")
    for i, (title, _) in enumerate(COLUMNS):
        table.add_column(title, justify="right" if i >= _NUMERIC_FROM else "left")
    for run in _sorted_runs(report):
        table.add_row(*(render(run) for _, render in COLUMNS))
    return table
