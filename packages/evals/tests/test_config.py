from __future__ import annotations

from pathlib import Path

import pytest
from llm_evals.config import Backend, EvalConfig
from llm_evals.suite import SUITE_NAMES
from pydantic import ValidationError

SHIPPED = Path(__file__).resolve().parents[3] / "configs" / "evals.yaml"


def test_shipped_config_is_valid() -> None:
    config = EvalConfig.load(SHIPPED)
    assert {"llamacpp", "llamacpp-think", "llamacpp-think-sampled"} <= set(config.backends)
    for backend in config.backends.values():
        assert set(backend.suites or []) <= set(SUITE_NAMES)

    off = config.options_for(config.backends["llamacpp"])
    assert (off.temperature, off.max_tokens) == (0.0, 1024)
    sampled = config.options_for(config.backends["llamacpp-think-sampled"])
    assert (sampled.temperature, sampled.max_tokens, sampled.timeout_s) == (1.0, 7168, 900)


def test_backend_overrides_fall_back_to_defaults() -> None:
    config = EvalConfig.model_validate(
        {
            "defaults": {"concurrency": 3, "temperature": 0.7, "timeout_s": 10},
            "backends": {
                "a": {"base_url": "http://x/v1", "model": "m"},
                "b": {"base_url": "http://x/v1", "model": "m", "concurrency": 1, "temperature": 0},
            },
        }
    )
    a, b = config.backends["a"], config.backends["b"]
    assert (config.concurrency_for(a), config.concurrency_for(b)) == (3, 1)
    assert (config.options_for(a).timeout_s, config.options_for(a).temperature) == (10, 0.7)
    assert config.options_for(b).temperature == 0.0  # an explicit 0 is not "unset"


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Backend.model_validate({"base_url": "http://x/v1", "model": "m", "max_token": 5})
    with pytest.raises(ValidationError):
        EvalConfig.model_validate({"backends": {}})
