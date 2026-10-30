from __future__ import annotations

from pathlib import Path

import pytest
from llm_agent.config import ClientConfig


@pytest.fixture
def config() -> ClientConfig:
    return ClientConfig(base_url="http://fake/v1/", model="fake-model")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    return root
