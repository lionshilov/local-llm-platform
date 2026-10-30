from __future__ import annotations

import pytest
from llm_evals.config import Backend, RequestOptions


@pytest.fixture
def backend() -> Backend:
    return Backend(
        base_url="http://fake/v1/",
        model="fake-model",
        label="Fake",
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


@pytest.fixture
def options() -> RequestOptions:
    return RequestOptions(max_tokens=64, timeout_s=5.0, retries=2, retry_backoff_s=0.0)
