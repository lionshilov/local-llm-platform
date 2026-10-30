"""Which model endpoint to talk to, how to talk to it, and how long the agent may run."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

DEFAULT_BASE_URL = "http://127.0.0.1:8080/v1"
DEFAULT_MODEL = "qwen3.5-4b"


class ThinkingSwitch(StrEnum):
    """Request field(s) used to turn thinking on or off; each server reads a different one."""

    PORTABLE = "portable"  # both fields below: llama.cpp, MLX-LM, Ollama and the gateway
    TEMPLATE = "template"  # chat_template_kwargs.enable_thinking: llama.cpp, MLX-LM
    EFFORT = "effort"  # reasoning_effort: OpenAI-style, the gateway, Ollama, recent llama.cpp
    NONE = "none"  # send neither, for strict hosted APIs; the server default applies


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge ``override`` into a copy of ``base``; nested dicts are merged, not replaced."""
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = value
    return merged


class ClientConfig(BaseModel):
    """An OpenAI-compatible chat completions endpoint and the sampling settings to use."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(default=DEFAULT_BASE_URL, description="Base URL including /v1.")
    model: str = Field(default=DEFAULT_MODEL, description="Model id the server expects.")
    api_key: SecretStr | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0, description="Generation cap per model call.")
    think: bool = Field(default=False, description="Let reasoning models think before answering.")
    thinking_switch: ThinkingSwitch = ThinkingSwitch.PORTABLE
    extra_body: dict[str, Any] = Field(
        default_factory=dict,
        description="Merged last into every request body, e.g. {'top_k': 20}.",
    )
    timeout_s: float = Field(default=300.0, gt=0, description="HTTP timeout per model call.")

    @field_validator("base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    def thinking_fields(self) -> dict[str, Any]:
        template = {"chat_template_kwargs": {"enable_thinking": self.think}}
        effort = {"reasoning_effort": "medium" if self.think else "none"}
        match self.thinking_switch:
            case ThinkingSwitch.PORTABLE:
                return {**template, **effort}
            case ThinkingSwitch.TEMPLATE:
                return template
            case ThinkingSwitch.EFFORT:
                return effort
            case ThinkingSwitch.NONE:
                return {}

    def request_fields(self) -> dict[str, Any]:
        """Body fields added to every request besides ``model``, ``messages`` and ``tools``."""
        base = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **self.thinking_fields(),
        }
        return deep_merge(base, self.extra_body)


class AgentLimits(BaseModel):
    """Hard limits that keep a misbehaving model from looping or hanging forever."""

    model_config = ConfigDict(extra="forbid")

    max_steps: int = Field(default=10, ge=1, description="Model calls per run.")
    tool_timeout_s: float = Field(default=30.0, gt=0, description="Per tool call.")
    time_budget_s: float = Field(default=300.0, gt=0, description="Wall clock for the whole run.")
    max_tool_output_chars: int = Field(
        default=8000, ge=100, description="Tool output beyond this is truncated before the model."
    )
