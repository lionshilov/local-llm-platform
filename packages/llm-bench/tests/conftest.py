from __future__ import annotations

import pytest
from llm_bench.config import Engine


@pytest.fixture
def engine() -> Engine:
    return Engine(
        base_url="http://fake/v1/",
        model="fake-model",
        label="Fake",
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
