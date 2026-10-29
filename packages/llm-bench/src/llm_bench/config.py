"""Benchmark configuration: which engines to hit and which load scenarios to run."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Engine(BaseModel):
    """An OpenAI-compatible inference endpoint serving one model."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(description="Base URL including the /v1 prefix.")
    model: str = Field(description="Model id as the server expects it in the request body.")
    label: str = Field(default="", description="Human-readable name used in reports.")
    api_key_env: str | None = Field(
        default=None, description="Name of the env var holding the API key, if any."
    )
    extra_body: dict[str, Any] = Field(
        default_factory=dict,
        description="Engine-specific request fields, e.g. chat_template_kwargs.",
    )

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None


class Scenario(BaseModel):
    """A load shape: prompt size, generation length and concurrency sweep."""

    model_config = ConfigDict(extra="forbid")

    description: str = ""
    prompt_words: int = Field(gt=0, description="Approximate size of the synthetic prompt.")
    max_tokens: int = Field(gt=0)
    concurrency: list[int] = Field(default_factory=lambda: [1], min_length=1)
    requests_per_level: int | None = Field(
        default=None,
        gt=0,
        description="Requests per concurrency level. Defaults to max(4, 2 * concurrency).",
    )

    @field_validator("concurrency")
    @classmethod
    def _positive_levels(cls, value: list[int]) -> list[int]:
        if any(level < 1 for level in value):
            raise ValueError("concurrency levels must be >= 1")
        return value

    def requests_for(self, concurrency: int) -> int:
        return self.requests_per_level or max(4, 2 * concurrency)


class BenchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engines: dict[str, Engine]
    scenarios: dict[str, Scenario]

    @classmethod
    def load(cls, path: Path) -> BenchConfig:
        with path.open() as fh:
            return cls.model_validate(yaml.safe_load(fh))
