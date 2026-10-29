"""FastAPI application: OpenAI-compatible routes, streaming relay, metrics and the chat UI."""

from __future__ import annotations

import asyncio
import functools
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from llm_gateway import __version__
from llm_gateway.admission import Admission, Slot
from llm_gateway.config import Backend, GatewayConfig
from llm_gateway.metrics import GatewayMetrics
from llm_gateway.normalize import apply_reasoning_effort, has_generated_text, normalize_payload

Json = dict[str, Any]


@dataclass
class _Retryable:
    """A failure that happened before any token was sent, so a fallback may take over."""

    response: Response


def _error(
    status: int, message: str, kind: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    """OpenAI-style error body, so SDK clients surface the message properly."""
    return JSONResponse(
        {"error": {"message": message, "type": kind}}, status_code=status, headers=headers
    )


def _waiting(admission: Admission) -> float:
    return admission.waiting


def _sse(payload: Json) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


def _auth_headers(backend: Backend) -> dict[str, str]:
    return {"Authorization": f"Bearer {backend.api_key}"} if backend.api_key else {}


class Gateway:
    def __init__(self, config: GatewayConfig, client: httpx.AsyncClient) -> None:
        self.config = config
        self.client = client
        self.metrics = GatewayMetrics()
        self.admissions = {
            name: Admission(b.max_concurrency, b.max_queue, b.queue_timeout_s)
            for name, b in config.backends.items()
        }
        for name, admission in self.admissions.items():
            self.metrics.queue_depth.labels(name).set_function(
                functools.partial(_waiting, admission)
            )

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

        # Try the requested backend, then its fallbacks. Only failures that happen before
        # any token is sent are retried, so a client never sees two half-answers.
        failure: Response | None = None
        for name in [model_id, *backend.fallbacks]:
            if failure is not None:
                self.metrics.fallbacks.labels(model_id, name).inc()
            result = await self._try_backend(name, body, started)
            if not isinstance(result, _Retryable):
                return result
            failure = result.response
        assert failure is not None
        return failure

    async def _try_backend(self, name: str, body: Json, started: float) -> Response | _Retryable:
        backend = self.config.backends[name]
        slot = await self.admissions[name].acquire()
        if slot is None:
            self.metrics.requests.labels(name, "rejected").inc()
            return _Retryable(
                _error(
                    429,
                    f"backend '{name}' is at capacity, retry shortly",
                    "rate_limited",
                    headers={"Retry-After": "1", "X-Backend": name},
                )
            )

        streaming_started = False
        try:
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
                self.metrics.requests.labels(name, "upstream_unavailable").inc()
                return _Retryable(
                    _error(
                        502,
                        f"backend '{name}' is unreachable: {exc}",
                        "upstream_unavailable",
                        headers={"X-Backend": name},
                    )
                )

            if upstream.status_code != httpx.codes.OK:
                content = await upstream.aread()
                await upstream.aclose()
                self.metrics.requests.labels(name, f"upstream_{upstream.status_code}").inc()
                response = Response(
                    content,
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"),
                    headers={"X-Backend": name},
                )
                return _Retryable(response) if upstream.status_code >= 500 else response

            if not body.get("stream"):
                try:
                    payload = json.loads(await upstream.aread())
                finally:
                    await upstream.aclose()
                self._record_usage(name, payload.get("usage"))
                self.metrics.requests.labels(name, "ok").inc()
                return JSONResponse(normalize_payload(payload, name), headers={"X-Backend": name})

            streaming_started = True
            return StreamingResponse(
                self._relay(upstream, name, started, slot),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Backend": name},
                # Also release here: if the client disconnects before the first chunk, the
                # generator never starts and its finally block never runs.
                background=BackgroundTask(slot.release),
            )
        finally:
            if not streaming_started:
                slot.release()

    async def _relay(
        self, upstream: httpx.Response, model_id: str, started: float, slot: Slot
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
            slot.release()
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
