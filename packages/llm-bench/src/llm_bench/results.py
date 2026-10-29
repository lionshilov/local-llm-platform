"""On-disk schema for benchmark results. Versioned so old result files stay readable."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from llm_bench.client import RequestResult
from llm_bench.metrics import LevelSummary

SCHEMA_VERSION = 1


class RunRecord(BaseModel):
    engine: str
    label: str
    model: str
    scenario: str
    prompt_words: int
    max_tokens: int
    concurrency: int
    summary: LevelSummary
    requests: list[RequestResult]


class BenchReport(BaseModel):
    schema_version: int = SCHEMA_VERSION
    created_at: datetime
    tool_version: str
    system: dict[str, Any]
    engines: dict[str, dict[str, Any]]
    runs: list[RunRecord] = []

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> BenchReport:
        return cls.model_validate_json(path.read_text())

    @classmethod
    def merge(cls, reports: list[BenchReport]) -> BenchReport:
        """Combine runs of the same benchmark executed per engine (see bench-all.sh)."""
        if not reports:
            raise ValueError("nothing to merge")
        first = min(reports, key=lambda r: r.created_at)
        merged = first.model_copy(update={"engines": {}, "runs": []})
        for report in reports:
            merged.engines.update(report.engines)
            merged.runs.extend(report.runs)
        return merged
