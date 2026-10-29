from __future__ import annotations

from pathlib import Path

import pytest
from llm_bench.config import BenchConfig, Engine, Scenario
from llm_bench.prompts import build_messages, synthetic_document
from pydantic import ValidationError

CONFIGS = Path(__file__).resolve().parents[3] / "configs"


@pytest.mark.parametrize("path", sorted(CONFIGS.glob("*.yaml")), ids=lambda p: p.name)
def test_shipped_configs_are_valid(path: Path) -> None:
    config = BenchConfig.load(path)
    assert config.engines
    assert config.scenarios


def test_scenario_defaults_scale_with_concurrency() -> None:
    scenario = Scenario(prompt_words=10, max_tokens=10, concurrency=[1, 8])
    assert scenario.requests_for(1) == 4
    assert scenario.requests_for(8) == 16
    assert Scenario(prompt_words=10, max_tokens=10, requests_per_level=3).requests_for(8) == 3


def test_invalid_config_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Scenario(prompt_words=10, max_tokens=10, concurrency=[0])
    with pytest.raises(ValidationError):
        Engine.model_validate({"base_url": "http://x/v1", "model": "m", "typo_field": 1})


def test_api_key_is_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BENCH_KEY", "secret")
    engine = Engine(base_url="http://x/v1/", model="m", api_key_env="BENCH_KEY")
    assert engine.api_key == "secret"
    assert engine.base_url == "http://x/v1"


def test_every_request_gets_a_unique_prefix() -> None:
    first = build_messages(prompt_words=20, index=0)[0]["content"]
    second = build_messages(prompt_words=20, index=0)[0]["content"]
    assert first != second
    assert first.splitlines()[1:] == second.splitlines()[1:]


def test_long_prompts_embed_a_document() -> None:
    content = build_messages(prompt_words=1000, index=3)[0]["content"]
    assert "Summarize the text above" in content
    assert 900 < len(content.split()) < 1100


def test_synthetic_document_is_deterministic() -> None:
    assert synthetic_document(100, seed=1) == synthetic_document(100, seed=1)
    assert synthetic_document(100, seed=1) != synthetic_document(100, seed=2)
