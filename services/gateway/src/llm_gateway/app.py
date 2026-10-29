"""FastAPI application: OpenAI-compatible routes, streaming relay, metrics and the chat UI."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from llm_gateway import __version__
from llm_gateway.config import Backend, GatewayConfig
from llm_gateway.metrics import GatewayMetrics
from llm_gateway.normalize import apply_reasoning_effort, has_generated_text, normalize_payload

Json = dict[str, Any]


def _error(status: int, message: str, kind: str) -> JSONResponse:
    """OpenAI-style error body, so SDK clients surface the message properly."""
    return JSONResponse({"error": {"message": message, "type": kind}}, status_code=status)


def _sse(payload: Json) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


def _auth_headers(backend: Backend) -> dict[str, str]:
    return {"Authorization": f"Bearer {backend.api_key}"} if backend.api_key else {}


class Gateway:
    def __init__(self, config: GatewayConfig, client: httpx.AsyncClient) -> None:
        self.config = config
        self.client = client
        self.metrics = GatewayMetrics()

    async def is_available(self, backend: Backend) -> bool:
        try:
            response = await self.client.get(
                f"{backend.base_url}/models", headers=_auth_headers(backend), timeout=2.0
            )
            response.raise_for_status()
            served = {m.get("id") for m in response.json().get("data", [])}
        except (httpx.HTTPError, ValueError, AttributeError):
            return False
        # Ollama lists every pulled model; others list what they serve.
        return not served or backend.model in served

    async def list_models(self) -> Json:
        backends = self.config.backends
        available = await asyncio.gather(*(self.is_available(b) for b in backends.values()))
        data = [
            {
                "id": name,
                "object": "model",
                "created": 0,
                "owned_by": backend.engine.value,
                "label": backend.label or name,
                "upstream_model": backend.model,
                "available": up,
            }
            for (name, backend), up in zip(backends.items(), available, strict=True)
        ]
        return {"object": "list", "data": data, "default": self.config.default_backend}

    async def chat_completions(self, body: Json) -> Response:
        started = time.perf_counter()
        model_id = body.get("model") or self.config.default_backend
        backend = self.config.backends.get(model_id) if isinstance(model_id, str) else None
        if backend is None or not isinstance(model_id, str):
            known = ", ".join(self.config.backends)
            return _error(404, f"model '{model_id}' not found; available: {known}", "not_found")

        upstream_body = apply_reasoning_effort({**body, "model": backend.model}, backend.engine)
        request = self.client.build_request(
            "POST",
            f"{backend.base_url}/chat/completions",
            json=upstream_body,
            headers=_auth_headers(backend),
        )
        try:
            upstream = await self.client.send(request, stream=True)
        except httpx.HTTPError as exc:
            self.metrics.requests.labels(model_id, "upstream_unavailable").inc()
            return _error(
                502, f"backend '{model_id}' is unreachable: {exc}", "upstream_unavailable"
            )

        if upstream.status_code != httpx.codes.OK:
            content = await upstream.aread()
            await upstream.aclose()
            self.metrics.requests.labels(model_id, f"upstream_{upstream.status_code}").inc()
            return Response(
                content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type"),
            )

        if not body.get("stream"):
            try:
                payload = json.loads(await upstream.aread())
            finally:
                await upstream.aclose()
            self._record_usage(model_id, payload.get("usage"))
            self.metrics.requests.labels(model_id, "ok").inc()
            return JSONResponse(normalize_payload(payload, model_id))

        return StreamingResponse(
            self._relay(upstream, model_id, started),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def _relay(
        self, upstream: httpx.Response, model_id: str, started: float
    ) -> AsyncIterator[bytes]:
        """Re-emit upstream SSE chunks in the gateway's format while timing them.

        If the client disconnects, the generator is closed, which closes the upstream
        connection; llama.cpp, MLX and Ollama all stop generating when that happens.
        """
        first_at: float | None = None
        last_at: float | None = None
        usage: Json | None = None
        outcome = "ok"
        self.metrics.in_flight.labels(model_id).inc()
        try:
            async for line in upstream.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                if not data:
                    continue
                chunk = normalize_payload(json.loads(data), model_id)
                if has_generated_text(chunk):
                    last_at = time.perf_counter()
                    first_at = first_at or last_at
                usage = chunk.get("usage") or usage
                yield _sse(chunk)
            yield b"data: [DONE]\n\n"
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            outcome = "upstream_error"
            yield _sse({"error": {"message": f"upstream stream failed: {exc}", "type": outcome}})
        except (asyncio.CancelledError, GeneratorExit):
            outcome = "cancelled"
            raise
        finally:
            await upstream.aclose()
            self.metrics.in_flight.labels(model_id).dec()
            self.metrics.requests.labels(model_id, outcome).inc()
            self._record_timing(model_id, started, first_at, last_at, usage)
            self._record_usage(model_id, usage)

    def _record_timing(
        self,
        model_id: str,
        started: float,
        first_at: float | None,
        last_at: float | None,
        usage: Json | None,
    ) -> None:
        if first_at is None:
            return
        self.metrics.ttft.labels(model_id).observe(first_at - started)
        completion_tokens = (usage or {}).get("completion_tokens") or 0
        if last_at is not None and completion_tokens > 1:
            tpot = (last_at - first_at) / (completion_tokens - 1)
            self.metrics.tpot.labels(model_id).observe(tpot)

    def _record_usage(self, model_id: str, usage: Json | None) -> None:
        if not usage:
            return
        self.metrics.prompt_tokens.labels(model_id).inc(usage.get("prompt_tokens") or 0)
        self.metrics.output_tokens.labels(model_id).inc(usage.get("completion_tokens") or 0)


def create_app(
    config: GatewayConfig,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    ui_dir: Path | None = None,
) -> FastAPI:
    client = httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(600.0, connect=5.0),
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
    )
    gateway = Gateway(config, client)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await client.aclose()

    app = FastAPI(title="llm-gateway", version=__version__, lifespan=lifespan)
    app.state.gateway = gateway

    @app.get("/healthz")
    async def healthz() -> Json:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = gateway.metrics.render()
        return Response(body, media_type=content_type)

    @app.get("/v1/models")
    async def list_models() -> Json:
        return await gateway.list_models()

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        try:
            body = await request.json()
        except ValueError:
            return _error(400, "request body must be JSON", "invalid_request_error")
        if not isinstance(body, dict):
            return _error(400, "request body must be a JSON object", "invalid_request_error")
        return await gateway.chat_completions(body)

    if ui_dir is not None and ui_dir.is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

    return app
