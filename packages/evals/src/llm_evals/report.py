"""Render eval results as Markdown (docs, PRs) or a Rich table (terminal)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import suppress

from rich.table import Table

from llm_evals.reply import Reply
from llm_evals.results import EvalReport, TaskSummary
from llm_evals.scoring.structured import parse_json
from llm_evals.stats import mcnemar_exact
from llm_evals.suite import SUITE_NAMES


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _interval(summary: TaskSummary) -> str:
    return f"{summary.ci_low * 100:.0f}\u2013{summary.ci_high * 100:.0f}"  # en dash


def _accuracy(summary: TaskSummary) -> str:
    return f"{_pct(summary.accuracy)} ({_interval(summary)})"


def _num(value: float | None, digits: int = 0) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def _cell(text: str) -> str:
    """Plain text that is safe inside a Markdown table cell."""
    text = " ".join(text.split())
    return text.replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")


def _code(text: str) -> str:
    """Literal text in a code span, safe inside a table cell (GFM unescapes ``\\|`` there)."""
    text = " ⏎ ".join(line.strip() for line in text.strip().splitlines() if line.strip())
    return "`" + text.replace("`", "'").replace("|", "\\|") + "`" if text else "*(empty)*"


def _excerpt(reply: Reply | None, head: int = 140, tail: int = 80) -> str:
    if reply is None:
        return "-"
    if reply.tool_calls:
        return _code("; ".join(f"{c.name}({c.arguments})" for c in reply.tool_calls))
    text = reply.content
    if not text and reply.reasoning:  # e.g. thinking ran out of max_tokens before answering
        return "*(no answer)*, reasoning ends " + _code("…" + reply.reasoning[-tail:])
    with suppress(ValueError):  # JSON reads better re-serialized on one line
        text = json.dumps(parse_json(text), ensure_ascii=False, separators=(",", ":"))
    if len(text) > head + tail + 5:
        text = f"{text[:head]} … {text[-tail:]}"
    return _code(text)


def task_order(report: EvalReport) -> list[str]:
    """Suites in catalog order; tasks within a suite in definition order."""
    suite_rank = {name: i for i, name in enumerate(SUITE_NAMES)}
    task_rank = {task: i for info in report.suites.values() for i, task in enumerate(info.tasks)}
    tasks = {item.task: item.suite for item in report.items}
    return sorted(
        tasks,
        key=lambda t: (suite_rank.get(tasks[t], len(suite_rank)), task_rank.get(t, 0), t),
    )


def _backends(report: EvalReport) -> list[str]:
    ran = {item.backend for item in report.items}
    return [name for name in report.backends if name in ran]


def shared_tasks(report: EvalReport) -> list[str]:
    """Tasks every backend ran: the only fair basis for an overall score."""
    backends = _backends(report)
    return [
        task
        for task in task_order(report)
        if all(report.summary(backend, task) for backend in backends)
    ]


def macro_average(report: EvalReport, backend: str, tasks: Iterable[str]) -> float | None:
    """Mean of per-task accuracies, so a 40-item suite doesn't outweigh a 20-item one."""
    accuracies = [s.accuracy for task in tasks if (s := report.summary(backend, task))]
    return sum(accuracies) / len(accuracies) if accuracies else None


def _table(headers: list[str], rows: list[list[str]], left: int = 1) -> list[str]:
    align = ["---" if i < left else "---:" for i in range(len(headers))]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(align) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _header(report: EvalReport) -> list[str]:
    system = report.system
    rank = {name: i for i, name in enumerate(SUITE_NAMES)}
    suites = ", ".join(
        f"{name} ({info.items} items, `{info.fingerprint}`)"
        for name, info in sorted(report.suites.items(), key=lambda s: rank.get(s[0], len(rank)))
    )
    lines = [
        f"**Hardware:** {system.get('cpu')} · {system.get('memory_gb')} GB · {system.get('os')}  ",
        f"**Date:** {report.created_at:%Y-%m-%d %H:%M} UTC · llm-evals {report.tool_version}  ",
        f"**Suites:** {suites}",
        "",
    ]
    rows = []
    for name in _backends(report):
        info = report.backends[name]
        settings = f"max_tokens {info.max_tokens}, temperature {info.temperature:g}"
        if info.extra_body:
            settings += f", `{json.dumps(info.extra_body)}`"
        rows.append(
            [f"`{name}`", info.label or "-", f"`{info.model}`", info.server or "-", settings]
        )
    headers = ["Backend", "Label", "Model", "Server", "Request settings"]
    return lines + _table(headers, rows, left=len(headers))


def _accuracy_table(report: EvalReport) -> list[str]:
    backends = _backends(report)
    rows = []
    for task in task_order(report):
        summaries = [report.summary(backend, task) for backend in backends]
        sizes = {s.n for s in summaries if s}
        n = str(sizes.pop()) if len(sizes) == 1 else "varies"
        rows.append([task, n, *(_accuracy(s) if s else "-" for s in summaries)])
    shared = shared_tasks(report)
    if shared:
        averages = [macro_average(report, backend, shared) for backend in backends]
        label = f"**Macro average** ({len(shared)} shared task{'s' * (len(shared) > 1)})"
        rows.append([label, "", *(f"**{_pct(a)}**" if a is not None else "-" for a in averages)])
    return [
        "### Accuracy",
        "",
        "Pass rate with 95% Wilson interval. Request errors count as failures.",
        "",
        *_table(["Task", "n", *(f"`{b}`" for b in backends)], rows),
    ]


def _cost_table(report: EvalReport) -> list[str]:
    rows = []
    for task in task_order(report):
        for backend in _backends(report):
            if s := report.summary(backend, task):
                rows.append(
                    [
                        task,
                        f"`{backend}`",
                        _num(s.latency_s_mean, 1),
                        _num(s.prompt_tokens_mean),
                        _num(s.completion_tokens_mean),
                        f"{s.errors}/{s.n}",
                    ]
                )
    return [
        "### Cost per item",
        "",
        "Means per item. Latency is end-to-end at the run's concurrency, on a server that may",
        "be shared: indicative only (llm-bench measures speed properly).",
        "",
        *_table(
            ["Task", "Backend", "Latency s", "Prompt tok", "Completion tok", "Errors"], rows, left=2
        ),
    ]


def paired(report: EvalReport, baseline: str, other: str, task: str) -> tuple[int, int, int]:
    """(items compared, only ``other`` passed, only ``baseline`` passed)."""
    base = {i.item_id: i.passed for i in report.items if i.backend == baseline and i.task == task}
    rest = {i.item_id: i.passed for i in report.items if i.backend == other and i.task == task}
    common = base.keys() & rest.keys()
    wins = sum(rest[i] and not base[i] for i in common)
    losses = sum(base[i] and not rest[i] for i in common)
    return len(common), wins, losses


def _paired_table(report: EvalReport) -> list[str]:
    backends = _backends(report)
    if len(backends) < 2:
        return []
    baseline, others = backends[0], backends[1:]
    rows = []
    for task in task_order(report):
        for other in others:
            n, wins, losses = paired(report, baseline, other, task)
            if n:
                delta = (wins - losses) / n * 100
                p_value = mcnemar_exact(wins, losses)
                row = [task, f"`{other}`", str(n), f"{delta:+.0f} pp", str(wins), str(losses)]
                rows.append([*row, f"{p_value:.2g}"])
    if not rows:
        return []
    return [
        f"### Paired comparison vs `{baseline}`",
        "",
        "Same items, so only disagreements carry information: *wins* are items only this",
        "backend passed, *losses* items only the baseline passed. p: two-sided exact McNemar.",
        "",
        *_table(["Task", "Backend", "Items", "Δ", "Wins", "Losses", "p"], rows, left=2),
    ]


def _breakdown_table(report: EvalReport) -> list[str]:
    backends = _backends(report)
    rows = []
    for task in task_order(report):
        names: dict[str, None] = {}
        for backend in backends:
            if s := report.summary(backend, task):
                names.update(dict.fromkeys(s.checks))
        for check in names:
            cells = []
            for backend in backends:
                s = report.summary(backend, task)
                rate = s.checks.get(check) if s else None
                cells.append(f"{rate.passed}/{rate.total}" if rate else "-")
            rows.append([task, check, *cells])
    if not rows:
        return []
    return [
        "### Sub-checks",
        "",
        "`format`: answer given in the requested `Answer:` form. `decision`/`function`/",
        "`arguments`: whether to call, which tool, what arguments. Instructions: per-type",
        "pass counts (instruction-level accuracy).",
        "",
        *_table(["Task", "Check", *(f"`{b}`" for b in backends)], rows, left=2),
    ]


def _failures(report: EvalReport, per_group: int) -> list[str]:
    if per_group <= 0:
        return []
    lines = ["### Failures", ""]
    for backend in _backends(report):
        for task in task_order(report):
            failed = [
                i for i in report.items if i.backend == backend and i.task == task and not i.passed
            ]
            if not failed:
                continue
            total = sum(1 for i in report.items if i.backend == backend and i.task == task)
            rows = [
                [f"`{i.item_id}`", _cell(i.reason or "-"), _excerpt(i.reply)]
                for i in failed[:per_group]
            ]
            more = len(failed) - per_group
            lines += [
                f"<details><summary><code>{backend}</code> · {task}: "
                f"{len(failed)} of {total} failed</summary>",
                "",
                *_table(["Item", "Reason", "Reply (excerpt)"], rows, left=3),
                *(["", f"…and {more} more in the JSON file."] if more > 0 else []),
                "",
                "</details>",
                "",
            ]
    return lines if len(lines) > 2 else []


def baseline_first(report: EvalReport, baseline: str | None) -> EvalReport:
    """Put ``baseline`` in the first column; it is what the other backends are tested against."""
    if baseline is None:
        return report
    if baseline not in report.backends:
        raise ValueError(f"unknown baseline '{baseline}'; backends: {', '.join(report.backends)}")
    backends = {baseline: report.backends[baseline], **report.backends}
    return report.model_copy(update={"backends": backends})


def to_markdown(report: EvalReport, failures: int = 3, baseline: str | None = None) -> str:
    """Full report. ``baseline`` is the backend others are tested against (default: first)."""
    report = baseline_first(report, baseline)
    blocks = [
        _header(report),
        _accuracy_table(report),
        _cost_table(report),
        _paired_table(report),
        _breakdown_table(report),
        _failures(report, failures),
    ]
    return "\n\n".join("\n".join(block).rstrip() for block in blocks if block) + "\n"


def to_rich_table(report: EvalReport) -> Table:
    table = Table(title="llm-evals results", header_style="bold cyan")
    headers = ["Task", "Backend", "Accuracy", "95% CI", "Passed", "Errors"]
    headers += ["Latency s", "Completion tok"]
    for i, header in enumerate(headers):
        table.add_column(header, justify="left" if i < 2 else "right")
    for task in task_order(report):
        for backend in _backends(report):
            if s := report.summary(backend, task):
                table.add_row(
                    task,
                    backend,
                    _pct(s.accuracy),
                    _interval(s),
                    f"{s.passed}/{s.n}",
                    str(s.errors),
                    _num(s.latency_s_mean, 1),
                    _num(s.completion_tokens_mean),
                )
    return table
