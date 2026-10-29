from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from llm_bench.testing import FakeServer
from llm_gateway.app import create_app
from llm_gateway.config import Backend, EngineKind, GatewayConfig

CONFIGS = Path(__file__).resolve().parents[3] / "configs"


def make_config() -> GatewayConfig:
    return GatewayConfig(
        default_backend="cpp",
        backends={
            "cpp": Backend(
                engine=EngineKind.LLAMACPP, base_url="http://fake/v1", model="fake-model"
            ),
            "olla": Backend(
                engine=EngineKind.OLLAMA,
                base_url="http://fake/v1",
                model="fake-model",
                label="Ollama",
            ),
            "down": Backend(engine=EngineKind.MLX, base_url="http://down/v1", model="m"),
        },
    )


@pytest.fixture
def server() -> FakeServer:
    return FakeServer(tokens=4)


@pytest.fixture
async def client(server: FakeServer) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_config(), transport=server.transport())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as c:
        yield c


def sse_payloads(text: str) -> list[Any]:
    lines = [line.removeprefix("data: ") for line in text.splitlines() if line.startswith("data: ")]
    return [line if line == "[DONE]" else json.loads(line) for line in lines]


async def test_models_report_availability(client: httpx.AsyncClient) -> None:
    response = await client.get("/v1/models")

    assert response.status_code == 200
    models = {m["id"]: m for m in response.json()["data"]}
    assert models["cpp"]["available"] is True
    assert models["olla"]["label"] == "Ollama"
    assert models["olla"]["owned_by"] == "ollama"
    assert models["down"]["available"] is False
    assert response.json()["default"] == "cpp"


async def test_streaming_relays_chunks_and_rewrites_model(
    client: httpx.AsyncClient, server: FakeServer
) -> None:
    body = {"model": "cpp", "messages": [{"role": "user", "content": "hi"}], "stream": True}
    response = await client.post("/v1/chat/completions", json=body)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    payloads = sse_payloads(response.text)
    assert payloads[-1] == "[DONE]"
    chunks = payloads[:-1]
    assert all(chunk["model"] == "cpp" for chunk in chunks)
    text = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks if c["choices"])
    assert text == "tok0 tok1 tok2 tok3 "
    assert server.requests[0]["model"] == "fake-model"


async def test_reasoning_field_is_normalized() -> None:
    server = FakeServer(tokens=2, text_field="reasoning")
    app = create_app(make_config(), transport=server.transport())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        body = {"model": "olla", "messages": [], "stream": True}
        response = await client.post("/v1/chat/completions", json=body)

    deltas = [c["choices"][0]["delta"] for c in sse_payloads(response.text)[:-1] if c["choices"]]
    assert deltas[0] == {"reasoning_content": "tok0 "}
    assert all("reasoning" not in d for d in deltas)


@pytest.mark.parametrize(
    ("model", "effort", "expected"),
    [
        ("cpp", "none", {"chat_template_kwargs": {"enable_thinking": False}}),
        ("cpp", "high", {"chat_template_kwargs": {"enable_thinking": True}}),
        ("olla", "none", {"reasoning_effort": "none"}),
        ("olla", "medium", {"reasoning_effort": "medium"}),
    ],
)
async def test_reasoning_effort_is_translated_per_engine(
    client: httpx.AsyncClient,
    server: FakeServer,
    model: str,
    effort: str,
    expected: dict[str, Any],
) -> None:
    body = {"model": model, "messages": [], "stream": True, "reasoning_effort": effort}
    await client.post("/v1/chat/completions", json=body)

    sent = server.requests[0]
    for key, value in expected.items():
        assert sent[key] == value
    if model == "cpp":
        assert "reasoning_effort" not in sent


async def test_non_streaming_is_normalized(client: httpx.AsyncClient) -> None:
    body = {"model": "cpp", "messages": [], "stream": False}
    response = await client.post("/v1/chat/completions", json=body)

    assert response.status_code == 200
    assert response.json()["model"] == "cpp"
    assert response.json()["choices"][0]["message"]["content"] == "tok0 tok1 tok2 tok3 "


async def test_default_backend_is_used_without_model(
    client: httpx.AsyncClient, server: FakeServer
) -> None:
    await client.post("/v1/chat/completions", json={"messages": [], "stream": True})
    assert server.requests[0]["model"] == "fake-model"


async def test_unknown_model_is_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/chat/completions", json={"model": "gpt-9", "messages": []})

    assert response.status_code == 404
    assert "gpt-9" in response.json()["error"]["message"]


async def test_unreachable_backend_is_502(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/chat/completions", json={"model": "down", "messages": []})

    assert response.status_code == 502
    assert response.json()["error"]["type"] == "upstream_unavailable"


async def test_invalid_body_is_400(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/chat/completions", content=b"not json")
    assert response.status_code == 400


async def test_metrics_are_exported(client: httpx.AsyncClient) -> None:
    body = {"model": "cpp", "messages": [], "stream": True}
    await client.post("/v1/chat/completions", json=body)

    text = (await client.get("/metrics")).text
    assert 'llm_gateway_requests_total{backend="cpp",outcome="ok"} 1.0' in text
    assert 'llm_gateway_output_tokens_total{backend="cpp"} 4.0' in text
    assert 'llm_gateway_time_to_first_token_seconds_count{backend="cpp"} 1.0' in text
    assert 'llm_gateway_in_flight_requests{backend="cpp"} 0.0' in text


async def test_ui_is_served_when_built(tmp_path: Path, server: FakeServer) -> None:
    (tmp_path / "index.html").write_text("<h1>chat</h1>")
    app = create_app(make_config(), transport=server.transport(), ui_dir=tmp_path)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        assert (await client.get("/")).text == "<h1>chat</h1>"
        assert (await client.get("/healthz")).json() == {"status": "ok"}


def test_shipped_config_is_valid() -> None:
    config = GatewayConfig.load(CONFIGS / "gateway.yaml")
    assert config.default_backend in config.backends


def test_default_backend_must_exist() -> None:
    with pytest.raises(ValueError, match="default_backend"):
        GatewayConfig(
            default_backend="nope",
            backends={"a": Backend(engine=EngineKind.OPENAI, base_url="http://x/v1", model="m")},
        )
