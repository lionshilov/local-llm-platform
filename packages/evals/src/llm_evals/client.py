"""Non-streaming chat completions over raw HTTP.

Quality evals don't need token timing, so a single JSON response is simpler than SSE and
gives assembled tool calls for free. Only connection-level failures are retried: those never
reached the model. A timeout or an HTTP error is a result, and retrying it would hide
problems and double the load on a shared server.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from llm_evals.config import Backend, RequestOptions
from llm_evals.reply import Reply

_TRANSIENT = (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError)


class ChatError(Exception):
    """The request produced no usable completion."""


@dataclass(frozen=True)
class ChatRequest:
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    response_format: dict[str, Any] | None = None

    @property
    def prompt(self) -> str:
        """The last user message, which is what result files record."""
        users = [m.get("content", "") for m in self.messages if m.get("role") == "user"]
        return str(users[-1]) if users else ""


def build_body(backend: Backend, request: ChatRequest, options: RequestOptions) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": backend.model,
        "messages": request.messages,
        "max_tokens": options.max_tokens,
        "temperature": options.temperature,
        "stream": False,
    }
    if request.tools is not None:
        body["tools"] = request.tools
    if request.response_format is not None:
        body["response_format"] = request.response_format
    return {**body, **backend.extra_body}


async def complete(
    client: httpx.AsyncClient, backend: Backend, request: ChatRequest, options: RequestOptions
) -> Reply:
    """Send one chat completion; raise ``ChatError`` if no completion comes back."""
    headers = {"Authorization": f"Bearer {backend.api_key}"} if backend.api_key else {}
    response = await _post(
        client,
        f"{backend.base_url}/chat/completions",
        build_body(backend, request, options),
        headers,
        options,
    )
    if response.status_code != httpx.codes.OK:
        raise ChatError(f"HTTP {response.status_code}: {response.text[:300]}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ChatError(f"response is not JSON: {response.text[:120]!r}") from exc
    if not isinstance(payload, dict) or "error" in payload:
        raise ChatError(f"server error: {str(payload)[:300]}")
    return Reply.from_openai(payload)


async def _post(
    client: httpx.AsyncClient,
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    options: RequestOptions,
) -> httpx.Response:
    for attempt in range(options.retries + 1):
        try:
            async with asyncio.timeout(options.timeout_s):
                return await client.post(url, json=body, headers=headers)
        except TimeoutError:
            raise ChatError(f"timed out after {options.timeout_s:g} s") from None
        except _TRANSIENT as exc:
            if attempt == options.retries:
                raise ChatError(f"{type(exc).__name__}: {exc}") from exc
            await asyncio.sleep(options.retry_backoff_s * 2**attempt)
        except httpx.HTTPError as exc:
            raise ChatError(f"{type(exc).__name__}: {exc}") from exc
    raise AssertionError("unreachable: the last attempt returns or raises")
