"""The agent loop: model -> tool calls -> tool results -> model -> ... -> final answer.

Each step is one chat completion with the tool schemas attached. If the reply contains
``tool_calls``, every call is validated and executed (concurrently), each result goes back
as a ``role: "tool"`` message carrying the ``tool_call_id`` it answers, and the model is
called again. A reply without tool calls is the final answer. ``max_steps``, a per-tool
timeout and a wall-clock budget bound the run; tool failures are returned to the model as
results, so only the model endpoint itself can end a run early.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel

from llm_agent.client import ChatClient, Completion, ModelError
from llm_agent.config import AgentLimits, ClientConfig
from llm_agent.events import (
    Event,
    EventHandler,
    FinalAnswer,
    ModelCalled,
    RunFailed,
    RunFinished,
    RunStarted,
    RunStatus,
    ToolCalled,
    ToolReturned,
)
from llm_agent.messages import Message, ToolCall, Usage
from llm_agent.prompts import build_system_prompt
from llm_agent.tools.base import AnyTool
from llm_agent.tools.registry import ToolRegistry, ToolResult


class Step(BaseModel):
    """One model call and the tool calls it requested."""

    index: int
    latency_s: float
    usage: Usage
    finish_reason: str | None
    content: str
    reasoning: str | None = None
    tool_calls: list[ToolCall] = []
    tool_results: list[ToolResult] = []
    server_timings: dict[str, Any] | None = None


class RunResult(BaseModel):
    run_id: str
    task: str
    model: str
    status: RunStatus
    answer: str | None
    error: str | None = None
    steps: list[Step]
    usage: Usage
    elapsed_s: float
    messages: list[Message]

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.COMPLETED

    @property
    def tool_calls(self) -> int:
        return sum(len(step.tool_calls) for step in self.steps)


class _Emitter:
    """Stamps events with the run id and elapsed time, then hands them to every handler."""

    def __init__(self, handlers: Sequence[EventHandler]) -> None:
        self.run_id = uuid.uuid4().hex[:12]
        self.started = time.perf_counter()
        self.handlers = handlers

    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def __call__(self, event: Event) -> None:
        event.run_id = self.run_id
        event.elapsed_s = self.elapsed()
        for handler in self.handlers:
            handler(event)


class Agent:
    def __init__(
        self,
        config: ClientConfig | None = None,
        tools: Iterable[AnyTool] = (),
        *,
        limits: AgentLimits | None = None,
        system_prompt: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        on_event: Sequence[EventHandler] = (),
    ) -> None:
        self.config = config or ClientConfig()
        self.limits = limits or AgentLimits()
        self.registry = ToolRegistry(tools, max_output_chars=self.limits.max_tool_output_chars)
        self.system_prompt = (
            build_system_prompt(self.registry.names) if system_prompt is None else system_prompt
        )
        self.on_event = on_event
        self._http = http_client

    async def run(self, task: str) -> RunResult:
        if self._http is not None:
            return await self._run(task, ChatClient(self.config, self._http))
        async with httpx.AsyncClient() as http:
            return await self._run(task, ChatClient(self.config, http))

    async def _run(self, task: str, client: ChatClient) -> RunResult:
        emit = _Emitter(self.on_event)
        deadline = emit.started + self.limits.time_budget_s
        messages = [Message.system(self.system_prompt), Message.user(task)]
        tools = self.registry.schemas()
        steps: list[Step] = []
        answer: str | None = None
        status = RunStatus.MAX_STEPS
        error: str | None = f"no final answer after {self.limits.max_steps} steps"

        emit(
            RunStarted(
                task=task,
                model=self.config.model,
                base_url=self.config.base_url,
                tools=self.registry.names,
                started_at=datetime.now(UTC),
            )
        )
        for index in range(1, self.limits.max_steps + 1):
            try:
                completion = await self._complete(client, messages, tools, deadline)
            except TimeoutError:
                status = RunStatus.TIME_BUDGET
                error = f"time budget of {self.limits.time_budget_s:g} s exhausted"
                break
            except ModelError as exc:
                status, error = RunStatus.MODEL_ERROR, str(exc)
                break

            step = self._record_step(index, completion, emit)
            steps.append(step)
            messages.append(completion.message)
            if not step.tool_calls:
                answer = step.content.strip() or None
                if answer is None:
                    status = RunStatus.NO_ANSWER
                    error = "the model returned neither tool calls nor an answer"
                else:
                    status, error = RunStatus.COMPLETED, None
                break

            step.tool_results = await self._call_tools(index, step.tool_calls, deadline, emit)
            messages.extend(Message.tool(r.call_id, r.output) for r in step.tool_results)

        usage = sum((step.usage for step in steps), Usage())
        if answer is not None:
            emit(FinalAnswer(step=len(steps), answer=answer))
        else:
            emit(RunFailed(step=len(steps), status=status, message=error or status.value))
        result = RunResult(
            run_id=emit.run_id,
            task=task,
            model=self.config.model,
            status=status,
            answer=answer,
            error=error,
            steps=steps,
            usage=usage,
            elapsed_s=emit.elapsed(),
            messages=messages,
        )
        emit(
            RunFinished(status=status, steps=len(steps), tool_calls=result.tool_calls, usage=usage)
        )
        return result

    @staticmethod
    async def _complete(
        client: ChatClient,
        messages: list[Message],
        tools: list[dict[str, Any]],
        deadline: float,
    ) -> Completion:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError
        async with asyncio.timeout(remaining):
            return await client.complete(messages, tools)

    @staticmethod
    def _record_step(index: int, completion: Completion, emit: _Emitter) -> Step:
        message = completion.message
        step = Step(
            index=index,
            latency_s=completion.latency_s,
            usage=completion.usage,
            finish_reason=completion.finish_reason,
            content=message.content or "",
            reasoning=completion.reasoning,
            tool_calls=message.tool_calls or [],
            server_timings=completion.server_timings,
        )
        emit(
            ModelCalled(
                step=index,
                latency_s=step.latency_s,
                usage=step.usage,
                finish_reason=step.finish_reason,
                content=step.content,
                reasoning=step.reasoning,
                tool_calls=len(step.tool_calls),
                server_timings=step.server_timings,
            )
        )
        return step

    async def _call_tools(
        self, step: int, calls: list[ToolCall], deadline: float, emit: _Emitter
    ) -> list[ToolResult]:
        """Run all calls of one turn concurrently; results keep the order of the calls."""
        timeout_s = max(0.0, min(self.limits.tool_timeout_s, deadline - time.perf_counter()))

        async def run_one(call: ToolCall) -> ToolResult:
            result = await self.registry.call(call, timeout_s=timeout_s)
            emit(
                ToolReturned(
                    step=step,
                    call_id=result.call_id,
                    name=result.name,
                    ok=result.ok,
                    output=result.output,
                    error=result.error,
                    latency_s=result.latency_s,
                )
            )
            return result

        for call in calls:
            emit(
                ToolCalled(
                    step=step,
                    call_id=call.id,
                    name=call.function.name,
                    arguments=call.function.arguments,
                )
            )
        return list(await asyncio.gather(*(run_one(call) for call in calls)))
