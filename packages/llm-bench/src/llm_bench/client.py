"""Streaming chat-completions client that timestamps every token chunk.

We talk raw HTTP + SSE instead of using the OpenAI SDK so that timing is measured at the
socket boundary with no hidden buffering, retries or client-side parsing in the way.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from llm_bench.config import Engine

# Fields that carry generated text inside a streamed delta. Reasoning models emit
# "thinking" tokens under different names depending on the server:
# llama.cpp -> reasoning_content, Ollama / MLX -> reasoning.
_TEXT_DELTA_FIELDS = ("content", "reasoning_content", "reasoning")


class RequestResult(BaseModel):
    ok: bool
    e2e_s: float
    ttft_s: float | None = None
    decode_s: float | None = None
    output_tokens: int = 0
    prompt_tokens: int | None = None
    token_source: Literal["usage", "chunks"] = "chunks"
    finish_reason: str | None = None
    server_timings: dict[str, Any] | None = None
    error: str | None = None
    chunk_gaps_s: list[float] = Field(default_factory=list, exclude=True)

    @property
    def tpot_s(self) -> float | None:
        """Time per output token after the first one."""
        if self.decode_s is None or self.output_tokens < 2:
            return None
        return self.decode_s / (self.output_tokens - 1)

    @property
    def decode_tps(self) -> float | None:
        tpot = self.tpot_s
        return 1.0 / tpot if tpot else None

    @property
    def prefill_tps(self) -> float | None:
        """Approximate prompt-processing speed: prompt tokens / time to first token."""
        if not self.ttft_s or not self.prompt_tokens:
            return None
        return self.prompt_tokens / self.ttft_s


async def iter_sse_data(lines: AsyncIterator[str]) -> AsyncIterator[dict[str, Any]]:
    """Yield JSON payloads from an OpenAI-style Server-Sent Events stream."""
    async for line in lines:
        if not line.startswith("data:"):
            continue  # blank separators, ": keep-alive" comments, "event:" lines
        payload = line.removeprefix("data:").strip()
        if payload == "[DONE]":
            return
        if payload:
            yield json.loads(payload)


def build_request_body(
    engine: Engine, messages: list[dict[str, str]], max_tokens: int
) -> dict[str, Any]:
    return {
        "model": engine.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
        "stream_options": {"include_usage": True},
        **engine.extra_body,
    }


async def stream_chat(
    client: httpx.AsyncClient,
    engine: Engine,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> RequestResult:
    body = build_request_body(engine, messages, max_tokens)
    headers = {"Authorization": f"Bearer {engine.api_key}"} if engine.api_key else {}

    first_at: float | None = None
    last_at: float | None = None
    gaps: list[float] = []
    text_chunks = 0
    usage: dict[str, Any] | None = None
    timings: dict[str, Any] | None = None
    finish_reason: str | None = None

    start = time.perf_counter()
    try:
        async with client.stream(
            "POST", f"{engine.base_url}/chat/completions", json=body, headers=headers
        ) as response:
            if response.status_code != httpx.codes.OK:
                detail = (await response.aread()).decode(errors="replace")[:300]
                return _failure(start, f"HTTP {response.status_code}: {detail}")

            async for chunk in iter_sse_data(response.aiter_lines()):
                now = time.perf_counter()
                if "error" in chunk:
                    return _failure(start, f"server error: {chunk['error']}")
                usage = chunk.get("usage") or usage
                timings = chunk.get("timings") or timings
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    if any(delta.get(name) for name in _TEXT_DELTA_FIELDS):
                        if last_at is None:
                            first_at = now
                        else:
                            gaps.append(now - last_at)
                        last_at = now
                        text_chunks += 1
                    finish_reason = choice.get("finish_reason") or finish_reason
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return _failure(start, f"{type(exc).__name__}: {exc}")

    end = time.perf_counter()
    if first_at is None or last_at is None:
        return _failure(start, "stream finished without any generated tokens")

    completion_tokens = usage.get("completion_tokens") if usage else None
    return RequestResult(
        ok=True,
        e2e_s=end - start,
        ttft_s=first_at - start,
        decode_s=last_at - first_at,
        output_tokens=completion_tokens or text_chunks,
        prompt_tokens=usage.get("prompt_tokens") if usage else None,
        token_source="usage" if completion_tokens else "chunks",
        finish_reason=finish_reason,
        server_timings=timings,
        chunk_gaps_s=gaps,
    )


def _failure(start: float, error: str) -> RequestResult:
    return RequestResult(ok=False, e2e_s=time.perf_counter() - start, error=error)
