"""Structured trace events: everything a run does, as typed records and JSON Lines.

Handlers receive events synchronously, in order, as they happen. The CLI renders them
live; ``JsonlTrace`` writes one JSON object per line; ``read_trace`` loads them back.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import IO, Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, TypeAdapter

from llm_agent.messages import Usage
from llm_agent.tools.registry import ToolErrorKind


class RunStatus(StrEnum):
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"  # the model stopped with neither tool calls nor text
    MAX_STEPS = "max_steps"
    TIME_BUDGET = "time_budget"
    MODEL_ERROR = "model_error"


class _Event(BaseModel):
    run_id: str = ""
    elapsed_s: float = Field(default=0.0, description="Seconds since the run started.")


class RunStarted(_Event):
    type: Literal["run_started"] = "run_started"
    task: str
    model: str
    base_url: str
    tools: list[str]
    started_at: datetime


class ModelCalled(_Event):
    type: Literal["model_call"] = "model_call"
    step: int
    latency_s: float
    usage: Usage
    finish_reason: str | None
    content: str
    reasoning: str | None
    tool_calls: int
    server_timings: dict[str, Any] | None = None


class ToolCalled(_Event):
    type: Literal["tool_call"] = "tool_call"
    step: int
    call_id: str
    name: str
    arguments: str


class ToolReturned(_Event):
    type: Literal["tool_result"] = "tool_result"
    step: int
    call_id: str
    name: str
    ok: bool
    output: str
    error: ToolErrorKind | None
    latency_s: float


class FinalAnswer(_Event):
    type: Literal["final_answer"] = "final_answer"
    step: int
    answer: str


class RunFailed(_Event):
    type: Literal["error"] = "error"
    step: int
    status: RunStatus
    message: str


class RunFinished(_Event):
    type: Literal["run_finished"] = "run_finished"
    status: RunStatus
    steps: int
    tool_calls: int
    usage: Usage


Event = Annotated[
    RunStarted | ModelCalled | ToolCalled | ToolReturned | FinalAnswer | RunFailed | RunFinished,
    Field(discriminator="type"),
]
EventHandler = Callable[[Event], None]

_EVENT: TypeAdapter[Event] = TypeAdapter(Event)


class JsonlTrace:
    """Event handler appending one JSON line per event, flushed so a crash keeps the trace."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: IO[str] | None = None

    def __enter__(self) -> Self:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def __call__(self, event: Event) -> None:
        if self._file is None:
            raise RuntimeError("JsonlTrace must be used as a context manager")
        self._file.write(event.model_dump_json() + "\n")
        self._file.flush()


def read_trace(path: Path) -> list[Event]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [_EVENT.validate_json(line) for line in lines if line.strip()]
