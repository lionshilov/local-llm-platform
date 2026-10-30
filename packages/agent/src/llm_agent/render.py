"""Render agent events live in the terminal with Rich.

Tool calls of one step run concurrently, so results are printed as they arrive, each
tagged with its tool name, rather than forced into call order.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from rich.text import Text

from llm_agent.events import (
    Event,
    FinalAnswer,
    ModelCalled,
    RunFailed,
    RunFinished,
    RunStarted,
    ToolCalled,
    ToolReturned,
)
from llm_agent.messages import Usage


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_arguments(raw: str, value_limit: int = 80) -> str:
    """``{"a": 1, "b": "x"}`` -> ``a=1, b="x"``; malformed JSON is shown as is."""
    try:
        parsed: Any = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return shorten(raw, value_limit * 2)
    if not isinstance(parsed, dict):
        return shorten(raw, value_limit * 2)
    return ", ".join(
        f"{key}={shorten(json.dumps(value, ensure_ascii=False), value_limit)}"
        for key, value in parsed.items()
    )


def preview(text: str, max_lines: int = 4, width: int = 110) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()] or [""]
    shown = [shorten(line, width) for line in lines[:max_lines]]
    if len(lines) > max_lines:
        shown.append(f"… {len(lines) - max_lines} more line(s)")
    return "\n".join(shown)


def format_usage(usage: Usage) -> str:
    cached = f" ({usage.cached_tokens:,} cached)" if usage.cached_tokens else ""
    return f"{usage.prompt_tokens:,} in{cached} · {usage.completion_tokens:,} out"


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


class RichRenderer:
    """Event handler that prints each step as it happens and drives a status spinner."""

    def __init__(self, console: Console, *, status: Status | None = None) -> None:
        self.console = console
        self.status = status
        self._pending_tools = 0

    @property
    def _width(self) -> int:
        """Room for one preview line after the deepest indent."""
        return max(40, self.console.width - 8)

    def _set_status(self, message: str) -> None:
        if self.status is not None:
            self.status.update(message)

    def __call__(self, event: Event) -> None:
        match event:
            case RunStarted():
                self._run_started(event)
            case ModelCalled():
                self._model_called(event)
            case ToolCalled():
                budget = self._width - len(event.name)
                args = shorten(format_arguments(event.arguments), max(20, budget))
                self.console.print(
                    Text.assemble("  → ", (event.name, "bold cyan"), f"({args})"),
                    soft_wrap=True,
                )
            case ToolReturned():
                self._tool_returned(event)
            case FinalAnswer():
                self.console.print(
                    Panel(
                        Markdown(event.answer),
                        title="Answer",
                        title_align="left",
                        border_style="green",
                    )
                )
            case RunFailed():
                self.console.print(
                    Panel(
                        Text(event.message),
                        title=f"Stopped: {event.status}",
                        title_align="left",
                        border_style="red",
                    )
                )
            case RunFinished():
                self.console.print(
                    f"[dim]{event.status} · {event.steps} step(s) · {event.tool_calls} tool "
                    f"call(s) · {event.elapsed_s:.1f} s · {format_usage(event.usage)} tokens[/]"
                )

    def _run_started(self, event: RunStarted) -> None:
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="bold")
        grid.add_column()
        # Text(), not str: user and model strings must never be parsed as Rich markup.
        grid.add_row("Task", Text(event.task))
        grid.add_row("Model", Text(f"{event.model} @ {event.base_url}"))
        grid.add_row("Tools", Text(", ".join(event.tools) or "none"))
        self.console.print(Panel(grid, title="llm-agent", title_align="left", border_style="blue"))
        self._set_status("Step 1: waiting for the model…")

    def _model_called(self, event: ModelCalled) -> None:
        self.console.print(
            Text.assemble(
                (f"Step {event.step}", "bold magenta"),
                (f"  model {event.latency_s:.2f} s · {format_usage(event.usage)} tokens", "dim"),
            )
        )
        thoughts = []
        if event.reasoning:
            text = preview(event.reasoning, 3, self._width)
            thoughts.append(Text(_indent(text, "  ▸ "), style="dim italic"))
        if event.tool_calls and event.content.strip():
            text = preview(event.content, 3, self._width)
            thoughts.append(Text(_indent(text, "  "), style="italic"))
        if thoughts:
            self.console.print(Group(*thoughts))
        if event.tool_calls:
            self._pending_tools = event.tool_calls
            self._set_status(f"Step {event.step}: running {event.tool_calls} tool call(s)…")

    def _tool_returned(self, event: ToolReturned) -> None:
        mark, style = ("✓", "green") if event.ok else ("✗", "red")
        lines = preview(event.output, width=self._width).splitlines() or [""]
        first = shorten(lines[0], max(20, self._width - len(event.name) - 12))
        head = Text.assemble(
            "  ← ",
            (event.name, "cyan"),
            " ",
            (mark, f"bold {style}"),
            " ",
            (first, "" if event.ok else style),
            (f"  {event.latency_s * 1000:.0f} ms", "dim"),
        )
        self.console.print(head, soft_wrap=True)
        if len(lines) > 1:
            self.console.print(Text(_indent("\n".join(lines[1:]), "      "), style="dim"))
        self._pending_tools -= 1
        if self._pending_tools <= 0:
            self._set_status(f"Step {event.step + 1}: waiting for the model…")
