"""Admission control and fallback routing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from llm_bench.testing import FakeServer
from llm_gateway.admission import Admission
from llm_gateway.app import Gateway, create_app
from llm_gateway.config import Backend, EngineKind, GatewayConfig

STREAM = {"messages": [{"role": "user", "content": "hi"}], "stream": True}


def backend(host: str, **kwargs: Any) -> Backend:
    return Backend(
        engine=EngineKind.LLAMACPP, base_url=f"http://{host}/v1", model="fake-model", **kwargs
    )


def routing_transport(server: FakeServer) -> httpx.MockTransport:
    """'fake' is a healthy engine, 'broken' answers 500, 'bad' answers 400, others refuse."""

    def handle(request: httpx.Request) -> httpx.Response:
        match request.url.host:
            case "fake":
                return server.handler(request)
            case "broken":
                return httpx.Response(500, json={"error": "engine crashed"})
            case "bad":
                return httpx.Response(400, json={"error": "context too long"})
            case _:
                raise httpx.ConnectError("connection refused", request=request)

    return httpx.MockTransport(handle)


@pytest.fixture
async def gateway_client(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[httpx.AsyncClient, Gateway, FakeServer]]:
    config, server = request.param
    app = create_app(config, transport=routing_transport(server))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        yield client, app.state.gateway, server


def slow_server() -> FakeServer:
    return FakeServer(tokens=2, first_token_delay_s=0.3)


async def post(client: httpx.AsyncClient, model: str) -> httpx.Response:
    return await client.post("/v1/chat/completions", json={**STREAM, "model": model})


@pytest.mark.parametrize(
    "gateway_client",
    [(GatewayConfig(backends={"cpp": backend("fake", max_concurrency=1)}), slow_server())],
    indirect=True,
)
async def test_full_backend_rejects_with_retry_after(
    gateway_client: tuple[httpx.AsyncClient, Gateway, FakeServer],
) -> None:
    client, gateway, _ = gateway_client
    first = asyncio.create_task(post(client, "cpp"))
    await asyncio.sleep(0.05)

    rejected = await post(client, "cpp")

    assert rejected.status_code == 429
    assert rejected.headers["retry-after"] == "1"
    assert rejected.json()["error"]["type"] == "rate_limited"
    assert (await first).status_code == 200
    assert (await post(client, "cpp")).status_code == 200
    assert gateway.admissions["cpp"].in_use == 0


@pytest.mark.parametrize(
    "gateway_client",
    [
        (
            GatewayConfig(backends={"cpp": backend("fake", max_concurrency=1, max_queue=1)}),
            slow_server(),
        )
    ],
    indirect=True,
)
async def test_queued_request_waits_for_a_slot(
    gateway_client: tuple[httpx.AsyncClient, Gateway, FakeServer],
) -> None:
    client, gateway, server = gateway_client
    first = asyncio.create_task(post(client, "cpp"))
    await asyncio.sleep(0.05)

    second = await post(client, "cpp")

    assert second.status_code == 200
    assert (await first).status_code == 200
    assert len(server.requests) == 2
    assert gateway.admissions["cpp"].waiting == 0


@pytest.mark.parametrize(
    "gateway_client",
    [
        (
            GatewayConfig(
                backends={
                    "cpp": backend("fake", max_concurrency=1, max_queue=1, queue_timeout_s=0.05)
                }
            ),
            slow_server(),
        )
    ],
    indirect=True,
)
async def test_queue_wait_is_bounded(
    gateway_client: tuple[httpx.AsyncClient, Gateway, FakeServer],
) -> None:
    client, _, _ = gateway_client
    first = asyncio.create_task(post(client, "cpp"))
    await asyncio.sleep(0.05)

    assert (await post(client, "cpp")).status_code == 429
    await first


FALLBACK_CONFIG = GatewayConfig(
    backends={
        "primary-down": backend("down", fallbacks=["cpp"]),
        "primary-broken": backend("broken", fallbacks=["cpp"]),
        "primary-bad": backend("bad", fallbacks=["cpp"]),
        "cpp": backend("fake"),
    }
)


@pytest.mark.parametrize("gateway_client", [(FALLBACK_CONFIG, FakeServer(tokens=3))], indirect=True)
@pytest.mark.parametrize("primary", ["primary-down", "primary-broken"])
async def test_fallback_on_unreachable_or_failing_backend(
    gateway_client: tuple[httpx.AsyncClient, Gateway, FakeServer], primary: str
) -> None:
    client, _, _ = gateway_client
    response = await post(client, primary)

    assert response.status_code == 200
    assert response.headers["x-backend"] == "cpp"
    assert '"model":"cpp"' in response.text
    metrics = (await client.get("/metrics")).text
    assert (
        f'llm_gateway_fallbacks_total{{from_backend="{primary}",to_backend="cpp"}} 1.0' in metrics
    )


@pytest.mark.parametrize("gateway_client", [(FALLBACK_CONFIG, FakeServer())], indirect=True)
async def test_client_errors_are_not_retried(
    gateway_client: tuple[httpx.AsyncClient, Gateway, FakeServer],
) -> None:
    client, _, server = gateway_client
    response = await post(client, "primary-bad")

    assert response.status_code == 400
    assert response.headers["x-backend"] == "primary-bad"
    assert server.requests == []


@pytest.mark.parametrize(
    "gateway_client",
    [
        (
            GatewayConfig(
                backends={
                    "busy": backend("fake", max_concurrency=1, fallbacks=["spare"]),
                    "spare": backend("fake"),
                }
            ),
            slow_server(),
        )
    ],
    indirect=True,
)
async def test_full_backend_overflows_to_fallback(
    gateway_client: tuple[httpx.AsyncClient, Gateway, FakeServer],
) -> None:
    client, _, _ = gateway_client
    first = asyncio.create_task(post(client, "busy"))
    await asyncio.sleep(0.05)

    overflow = await post(client, "busy")

    assert overflow.status_code == 200
    assert overflow.headers["x-backend"] == "spare"
    assert (await first).headers["x-backend"] == "busy"


def test_invalid_fallback_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid fallback"):
        GatewayConfig(backends={"a": backend("x", fallbacks=["missing"])})
    with pytest.raises(ValueError, match="invalid fallback"):
        GatewayConfig(backends={"a": backend("x", fallbacks=["a"])})


async def test_slot_release_is_idempotent() -> None:
    admission = Admission(limit=1)
    slot = await admission.acquire()
    assert slot is not None
    assert await admission.acquire() is None

    slot.release()
    slot.release()

    assert admission.in_use == 0
    assert await admission.acquire() is not None
    assert await admission.acquire() is None


async def test_unlimited_admission_never_blocks() -> None:
    admission = Admission(limit=None)
    slots = [await admission.acquire() for _ in range(100)]
    assert all(slots)
    assert admission.in_use == 100
