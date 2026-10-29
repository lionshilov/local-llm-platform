"""Closed-loop load generation: N concurrent virtual users, each sending requests back to back."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import httpx

from llm_bench.client import RequestResult, stream_chat
from llm_bench.config import Engine, Scenario
from llm_bench.prompts import build_messages


async def run_level(
    client: httpx.AsyncClient,
    engine: Engine,
    scenario: Scenario,
    concurrency: int,
    requests: int,
    on_request_done: Callable[[RequestResult], None] | None = None,
) -> tuple[list[RequestResult], float]:
    """Send ``requests`` requests with at most ``concurrency`` in flight.

    Returns the per-request results and the wall-clock duration of the level.
    """
    gate = asyncio.Semaphore(concurrency)

    async def one(index: int) -> RequestResult:
        async with gate:
            messages = build_messages(scenario.prompt_words, index)
            result = await stream_chat(client, engine, messages, scenario.max_tokens)
        if on_request_done is not None:
            on_request_done(result)
        return result

    started = time.perf_counter()
    results = await asyncio.gather(*(one(i) for i in range(requests)))
    return list(results), time.perf_counter() - started


async def warm_up(client: httpx.AsyncClient, engine: Engine, rounds: int) -> list[RequestResult]:
    """Load the model into memory and compile kernels before anything is measured."""
    results = []
    for i in range(rounds):
        messages = build_messages(prompt_words=10, index=i)
        results.append(await stream_chat(client, engine, messages, max_tokens=16))
    return results
