from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from llm_evals.reply import Reply
from llm_evals.report import macro_average, paired, shared_tasks, task_order, to_markdown
from llm_evals.results import BackendInfo, EvalReport, ItemResult, SuiteInfo

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _item(backend: str, task: str, item_id: str, passed: bool, **extra: object) -> ItemResult:
    suite = task.split("/")[0]
    fields: dict[str, object] = {
        "reply": Reply(content=f"reply to {item_id}", completion_tokens=10),
        "reason": None if passed else "expected 1, got 2",
        **extra,
    }
    return ItemResult.model_validate(
        {
            "backend": backend,
            "suite": suite,
            "task": task,
            "item_id": item_id,
            "prompt": "p",
            "passed": passed,
            "latency_s": 1.5,
            **fields,
        }
    )


def _report(
    backend: str, results: dict[str, list[bool]], *, minutes: int = 0, fingerprint: str = "abc"
) -> EvalReport:
    report = EvalReport(
        created_at=T0 + timedelta(minutes=minutes),
        tool_version="0.1.0",
        system={"cpu": "Test CPU", "memory_gb": 16.0, "os": "TestOS"},
        backends={
            backend: BackendInfo(
                label=f"{backend} label",
                model="m",
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                max_tokens=1024,
                temperature=0,
            )
        },
        suites={
            "math": SuiteInfo(kind="math", items=10, fingerprint=fingerprint, tasks=["math"]),
            "json": SuiteInfo(
                kind="json",
                items=4,
                fingerprint="def",
                tasks=["json/prompted", "json/constrained"],
            ),
        },
    )
    report.add(
        _item(backend, task, f"{task}-{i}", ok)
        for task, oks in results.items()
        for i, ok in enumerate(oks)
    )
    return report


BASE = _report(
    "base",
    {
        "math": [True] * 6 + [False] * 4,
        "json/constrained": [True] * 4,
        "json/prompted": [False] * 4,
    },
)
THINK = _report("think", {"math": [True] * 10}, minutes=5)


def test_task_order_follows_catalog_and_definition_order() -> None:
    assert task_order(BASE) == ["math", "json/prompted", "json/constrained"]


def test_single_report_markdown() -> None:
    markdown = to_markdown(BASE)
    assert markdown.startswith("**Hardware:** Test CPU · 16.0 GB · TestOS")
    assert "**Suites:** math (10 items, `abc`)" in markdown
    assert "| math | 10 | 60% (31\u201383) |" in markdown
    assert "| **Macro average** (3 shared tasks) |  | **53%** |" in markdown
    assert '`{"chat_template_kwargs": {"enable_thinking": false}}`' in markdown
    assert "Paired comparison" not in markdown
    assert "<code>base</code> · math: 4 of 10 failed" in markdown
    assert "…and 1 more in the JSON file." in markdown


def test_merged_report_compares_backends_on_shared_tasks() -> None:
    merged = EvalReport.merge([THINK, BASE])
    assert merged.created_at == T0
    assert list(merged.backends) == ["base", "think"]
    assert shared_tasks(merged) == ["math"]
    assert macro_average(merged, "base", ["math"]) == pytest.approx(0.6)
    assert paired(merged, "base", "think", "math") == (10, 4, 0)

    markdown = to_markdown(merged, failures=0)
    assert "| json/prompted | 4 | 0% (0\u201349) | - |" in markdown
    assert "| **Macro average** (1 shared task) |  | **60%** | **100%** |" in markdown
    assert "| math | `think` | 10 | +40 pp | 4 | 0 | 0.12 |" in markdown
    assert "### Failures" not in markdown


def test_baseline_can_be_chosen() -> None:
    merged = EvalReport.merge([BASE, THINK])
    markdown = to_markdown(merged, baseline="think")
    assert "### Paired comparison vs `think`" in markdown
    assert "| Task | n | `think` | `base` |" in markdown
    assert "| math | `base` | 10 | -40 pp | 0 | 4 | 0.12 |" in markdown
    with pytest.raises(ValueError, match="unknown baseline 'nope'"):
        to_markdown(merged, baseline="nope")


def test_truncated_thinking_shows_how_reasoning_ended() -> None:
    report = _report("think", {"math": [True]})
    reply = Reply(
        content="", reasoning="Let me think... " * 50 + "so the total is", completion_tokens=7168
    )
    report.add(
        [_item("think", "math", "x", False, reply=reply, reason="no number [hit max_tokens]")]
    )
    assert "*(no answer)*, reasoning ends `…" in to_markdown(report)
    assert "so the total is`" in to_markdown(report)


def test_merge_refuses_duplicates_and_mismatched_suites() -> None:
    with pytest.raises(ValueError, match="appear twice"):
        EvalReport.merge([BASE, BASE])
    other_version = _report("other", {"math": [True]}, fingerprint="xyz")
    with pytest.raises(ValueError, match="suite 'math' differs"):
        EvalReport.merge([BASE, other_version])
    with pytest.raises(ValueError, match="nothing to merge"):
        EvalReport.merge([])


def test_failure_cells_are_escaped() -> None:
    report = _report("base", {"math": [True]})
    report.add(
        [
            _item(
                "base",
                "math",
                "x",
                False,
                reason="no <<title>> | here",
                reply=Reply(content="a | b\n`code`\n\nend"),
            )
        ]
    )
    markdown = to_markdown(report)
    assert "| `x` | no &lt;&lt;title&gt;&gt; \\| here | `a \\| b ⏎ 'code' ⏎ end` |" in markdown


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "r.json"
    BASE.save(path)
    assert EvalReport.load(path) == BASE
