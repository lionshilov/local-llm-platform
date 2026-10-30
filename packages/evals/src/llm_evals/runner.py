"""Run tasks against one backend with bounded concurrency and record every item."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from llm_evals.client import ChatError, complete
from llm_evals.config import Backend, RequestOptions
from llm_evals.reply import Reply
from llm_evals.results import EvalReport, ItemResult
from llm_evals.scoring import Score
from llm_evals.suite import Item, load_suites
from llm_evals.tasks import Task, tasks_for

OnResult = Callable[[ItemResult], None]


def score_reply[ItemT: Item](task: Task[ItemT], item: ItemT, reply: Reply) -> Score:
    score = task.score(item, reply)
    if not score.passed and reply.finish_reason == "length":
        return score.model_copy(update={"reason": f"{score.reason} [hit max_tokens]"})
    return score


async def evaluate_item[ItemT: Item](
    client: httpx.AsyncClient,
    backend_name: str,
    backend: Backend,
    task: Task[ItemT],
    item: ItemT,
    options: RequestOptions,
) -> ItemResult:
    """Ask, score, record. A failed request is a failed item, never a skipped one."""
    request = task.request(item)
    reply: Reply | None = None
    error: str | None = None
    started = time.perf_counter()
    try:
        reply = await complete(client, backend, request, options)
    except ChatError as exc:
        error = str(exc)
    latency = time.perf_counter() - started

    score = Score(passed=False, reason=error) if reply is None else score_reply(task, item, reply)

    return ItemResult(
        backend=backend_name,
        suite=task.suite,
        task=task.name,
        item_id=item.id,
        prompt=request.prompt,
        reply=reply,
        extracted=score.extracted,
        passed=score.passed,
        reason=score.reason,
        checks=score.checks,
        error=error,
        latency_s=latency,
    )


async def run_tasks(
    client: httpx.AsyncClient,
    backend_name: str,
    backend: Backend,
    tasks: Sequence[Task[Any]],
    options: RequestOptions,
    *,
    concurrency: int,
    limit: int | None = None,
    on_result: OnResult | None = None,
) -> list[ItemResult]:
    """Evaluate the first ``limit`` items of every task; results keep suite order."""
    gate = asyncio.Semaphore(concurrency)

    async def one(task: Task[Any], item: Item) -> ItemResult:
        async with gate:
            result = await evaluate_item(client, backend_name, backend, task, item, options)
        if on_result is not None:
            on_result(result)
        return result

    jobs = [one(task, item) for task in tasks for item in task.items[:limit]]
    return list(await asyncio.gather(*jobs))


def rescore(report: EvalReport) -> EvalReport:
    """Re-apply the current scorers to stored replies, without calling any model.

    Generation is slow and scoring is instant, so a scorer fix should never require a
    re-run. Refuses if a suite changed since the run: the stored replies would then answer
    different prompts.
    """
    suites = load_suites(list(report.suites))
    for name, info in report.suites.items():
        if suites[name].fingerprint != info.fingerprint:
            raise ValueError(
                f"suite '{name}' changed since this run "
                f"({info.fingerprint} -> {suites[name].fingerprint}); re-run instead"
            )
    tasks = {task.name: task for suite in suites.values() for task in tasks_for(suite)}
    items = {name: {item.id: item for item in task.items} for name, task in tasks.items()}

    rescored = []
    for result in report.items:
        if result.reply is None:
            rescored.append(result)
            continue
        score = score_reply(tasks[result.task], items[result.task][result.item_id], result.reply)
        rescored.append(
            result.model_copy(
                update={
                    "extracted": score.extracted,
                    "passed": score.passed,
                    "reason": score.reason,
                    "checks": score.checks,
                }
            )
        )
    updated = report.model_copy(update={"items": [], "summaries": []})
    updated.add(rescored)
    return updated
