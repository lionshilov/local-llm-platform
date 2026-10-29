from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from llm_bench.client import iter_sse_data, stream_chat
from llm_bench.config import Engine
from llm_bench.testing import FakeServer

MESSAGES = [{"role": "user", "content": "hi"}]


async def _lines(*lines: str) -> AsyncIterator[str]:
    for line in lines:
        yield line


async def test_iter_sse_data_skips_noise_and_stops_at_done() -> None:
    stream = _lines(
        ": comment",
        "",
        "event: message",
        'data: {"a": 1}',
        'data:{"b":2}',
        "data: [DONE]",
        'data: {"c": 3}',
    )
    assert [chunk async for chunk in iter_sse_data(stream)] == [{"a": 1}, {"b": 2}]


async def test_counts_tokens_from_usage_and_sends_extra_body(engine: Engine) -> None:
    server = FakeServer(tokens=7)
    async with server.client() as client:
        result = await stream_chat(client, engine, MESSAGES, max_tokens=16)

    assert result.ok, result.error
    assert result.output_tokens == 7
    assert result.prompt_tokens == 42
    assert result.token_source == "usage"
    assert result.finish_reason == "length"
    assert len(result.chunk_gaps_s) == 6

    body = server.requests[0]
    assert body["stream"] is True
    assert body["stream_options"] == {"include_usage": True}
    assert body["max_tokens"] == 16
    assert body["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.parametrize("text_field", ["reasoning_content", "reasoning"])
async def test_reasoning_tokens_count_as_output_without_usage(
    engine: Engine, text_field: str
) -> None:
    server = FakeServer(tokens=4, text_field=text_field, send_usage=False)
    async with server.client() as client:
        result = await stream_chat(client, engine, MESSAGES, max_tokens=16)

    assert result.ok
    assert result.output_tokens == 4
    assert result.token_source == "chunks"
    assert result.prompt_tokens is None


async def test_ttft_includes_server_delay(engine: Engine) -> None:
    server = FakeServer(first_token_delay_s=0.05)
    async with server.client() as client:
        result = await stream_chat(client, engine, MESSAGES, max_tokens=16)

    assert result.ttft_s is not None
    assert result.ttft_s >= 0.05
    assert result.decode_s is not None
    assert result.e2e_s >= result.ttft_s + result.decode_s
    assert result.tpot_s is not None
    assert result.decode_tps is not None


async def test_http_error_is_reported(engine: Engine) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(503, text="model loading"))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await stream_chat(client, engine, MESSAGES, max_tokens=16)

    assert not result.ok
    assert result.error == "HTTP 503: model loading"


async def test_error_chunk_in_stream_is_reported(engine: Engine) -> None:
    body = b'data: {"error": {"message": "context overflow"}}\n\n'
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=body))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await stream_chat(client, engine, MESSAGES, max_tokens=16)

    assert not result.ok
    assert result.error is not None
    assert "context overflow" in result.error


async def test_stream_without_tokens_is_a_failure(engine: Engine) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"data: [DONE]\n\n"))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await stream_chat(client, engine, MESSAGES, max_tokens=16)

    assert not result.ok
    assert result.error == "stream finished without any generated tokens"


async def test_connection_error_is_reported(engine: Engine) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(refuse)) as client:
        result = await stream_chat(client, engine, MESSAGES, max_tokens=16)

    assert not result.ok
    assert result.error == "ConnectError: connection refused"
