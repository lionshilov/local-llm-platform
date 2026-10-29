"""Gateway configuration: the upstream backends clients can address by name."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EngineKind(StrEnum):
    """Which server sits behind a backend; decides how engine quirks are translated."""

    LLAMACPP = "llamacpp"
    MLX = "mlx"
    OLLAMA = "ollama"
    OPENAI = "openai"  # any spec-compliant server or hosted API


class Backend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = ""
    engine: EngineKind
    base_url: str = Field(description="Upstream base URL including /v1.")
    model: str = Field(description="Model id the upstream server expects.")
    api_key_env: str | None = None

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backends: dict[str, Backend] = Field(min_length=1)
    default_backend: str | None = None

    @model_validator(mode="after")
    def _default_exists(self) -> GatewayConfig:
        if self.default_backend is not None and self.default_backend not in self.backends:
            raise ValueError(
                f"default_backend '{self.default_backend}' is not a configured backend"
            )
        return self

    @classmethod
    def load(cls, path: Path) -> GatewayConfig:
        with path.open() as fh:
            return cls.model_validate(yaml.safe_load(fh))
