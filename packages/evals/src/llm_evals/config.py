"""Eval configuration: which backends to evaluate and the request settings to use."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from llm_bench.config import Engine
from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class RequestOptions:
    """Resolved per-request settings for one backend."""

    max_tokens: int
    temperature: float = 0.0
    timeout_s: float = 300.0
    retries: int = 2
    retry_backoff_s: float = 1.0


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concurrency: int = Field(default=2, ge=1, description="Requests in flight per backend.")
    max_tokens: int = Field(default=1024, gt=0)
    temperature: float = Field(default=0.0, ge=0)
    timeout_s: float = Field(default=300.0, gt=0, description="Deadline per request.")
    retries: int = Field(default=2, ge=0, description="Retries on connection errors only.")


class Backend(Engine):
    """An OpenAI-compatible endpoint (llm-bench's ``Engine``) plus per-backend overrides."""

    concurrency: int | None = Field(default=None, ge=1)
    max_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0)
    timeout_s: float | None = Field(default=None, gt=0)
    suites: list[str] | None = Field(
        default=None, description="Suites run by default for this backend; all if omitted."
    )


class EvalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defaults: Defaults = Field(default_factory=Defaults)
    backends: dict[str, Backend] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path) -> EvalConfig:
        with path.open() as fh:
            return cls.model_validate(yaml.safe_load(fh))

    def options_for(self, backend: Backend) -> RequestOptions:
        return RequestOptions(
            max_tokens=backend.max_tokens or self.defaults.max_tokens,
            temperature=(
                self.defaults.temperature if backend.temperature is None else backend.temperature
            ),
            timeout_s=backend.timeout_s or self.defaults.timeout_s,
            retries=self.defaults.retries,
        )

    def concurrency_for(self, backend: Backend) -> int:
        return backend.concurrency or self.defaults.concurrency
