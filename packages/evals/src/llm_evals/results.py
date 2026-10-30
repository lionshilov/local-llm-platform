"""On-disk schema for eval results. Versioned so old result files stay readable.

Item-level records are the source of truth; summaries are derived from them and stored
only for the convenience of tools that read the JSON without this package.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, JsonValue

from llm_evals.reply import Reply
from llm_evals.stats import mean, wilson_interval

SCHEMA_VERSION = 1


class ItemResult(BaseModel):
    backend: str
    suite: str
    task: str
    item_id: str
    prompt: str
    reply: Reply | None = Field(description="None if the request failed.")
    extracted: JsonValue = None
    passed: bool
    reason: str | None = None
    checks: dict[str, bool] = Field(default_factory=dict)
    error: str | None = Field(default=None, description="Transport/server error, if any.")
    latency_s: float


class CheckRate(BaseModel):
    passed: int
    total: int


class TaskSummary(BaseModel):
    """Pass rate of one backend on one task. Errors count as failures."""

    backend: str
    task: str
    n: int
    passed: int
    errors: int
    accuracy: float
    ci_low: float
    ci_high: float
    latency_s_mean: float | None
    prompt_tokens_mean: float | None
    completion_tokens_mean: float | None
    checks: dict[str, CheckRate] = Field(default_factory=dict)


class BackendInfo(BaseModel):
    label: str
    model: str
    server: str | None = None
    extra_body: dict[str, Any] = Field(default_factory=dict)
    max_tokens: int
    temperature: float


class SuiteInfo(BaseModel):
    kind: str
    items: int
    fingerprint: str
    tasks: list[str]


def summarize_task(backend: str, task: str, items: list[ItemResult]) -> TaskSummary:
    passed = sum(item.passed for item in items)
    low, high = wilson_interval(passed, len(items))
    replies = [item.reply for item in items if item.reply is not None]

    checks: dict[str, CheckRate] = {}
    for item in items:
        for name, ok in item.checks.items():
            rate = checks.setdefault(name, CheckRate(passed=0, total=0))
            rate.passed += ok
            rate.total += 1

    return TaskSummary(
        backend=backend,
        task=task,
        n=len(items),
        passed=passed,
        errors=sum(item.error is not None for item in items),
        accuracy=passed / len(items) if items else 0.0,
        ci_low=low,
        ci_high=high,
        latency_s_mean=mean(item.latency_s for item in items if item.error is None),
        prompt_tokens_mean=mean(reply.prompt_tokens for reply in replies),
        completion_tokens_mean=mean(reply.completion_tokens for reply in replies),
        checks=checks,
    )


def summarize(items: Iterable[ItemResult]) -> list[TaskSummary]:
    groups: dict[tuple[str, str], list[ItemResult]] = defaultdict(list)
    for item in items:
        groups[item.backend, item.task].append(item)
    return [summarize_task(backend, task, group) for (backend, task), group in groups.items()]


class EvalReport(BaseModel):
    schema_version: int = SCHEMA_VERSION
    created_at: datetime
    tool_version: str
    system: dict[str, Any]
    backends: dict[str, BackendInfo] = Field(default_factory=dict)
    suites: dict[str, SuiteInfo] = Field(default_factory=dict)
    summaries: list[TaskSummary] = Field(default_factory=list)
    items: list[ItemResult] = Field(default_factory=list)

    def add(self, items: Iterable[ItemResult]) -> None:
        self.items.extend(items)
        self.summaries = summarize(self.items)

    def summary(self, backend: str, task: str) -> TaskSummary | None:
        return next(
            (s for s in self.summaries if s.backend == backend and s.task == task),
            None,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> EvalReport:
        return cls.model_validate_json(path.read_text())

    @classmethod
    def merge(cls, reports: list[EvalReport]) -> EvalReport:
        """Combine runs (e.g. one file per backend) into one comparable report.

        Refuses to mix different versions of a suite or duplicate (backend, task) results:
        either would make the comparison silently wrong.
        """
        if not reports:
            raise ValueError("nothing to merge")
        first = min(reports, key=lambda r: r.created_at)
        merged = first.model_copy(
            update={"backends": {}, "suites": {}, "summaries": [], "items": []}
        )
        seen: set[tuple[str, str]] = set()
        for report in sorted(reports, key=lambda r: r.created_at):
            for name, suite in report.suites.items():
                known = merged.suites.setdefault(name, suite)
                if known.fingerprint != suite.fingerprint:
                    raise ValueError(
                        f"suite '{name}' differs between result files "
                        f"({known.fingerprint} vs {suite.fingerprint}); re-run with one version"
                    )
            pairs = {(item.backend, item.task) for item in report.items}
            if duplicates := sorted(pairs & seen):
                backend, task = duplicates[0]
                raise ValueError(f"results for backend '{backend}' on '{task}' appear twice")
            seen |= pairs
            merged.backends.update(report.backends)
            merged.items.extend(report.items)
        merged.summaries = summarize(merged.items)
        return merged
