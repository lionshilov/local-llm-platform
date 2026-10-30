"""Built-in tools, grouped so the CLI can enable them by name (``--tools calculator,files``)."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

import httpx

from llm_agent.tools.base import AnyTool
from llm_agent.tools.calculator import calculator
from llm_agent.tools.clock import current_time
from llm_agent.tools.files import Workspace
from llm_agent.tools.python import PythonRunner
from llm_agent.tools.web import HttpFetcher


class ToolGroup(StrEnum):
    CALCULATOR = "calculator"
    FILES = "files"
    PYTHON = "python"
    HTTP = "http"
    TIME = "time"


# python and http reach beyond the workspace (processes, network), so they are opt-in.
DEFAULT_GROUPS: tuple[ToolGroup, ...] = (ToolGroup.CALCULATOR, ToolGroup.FILES, ToolGroup.TIME)


def builtin_tools(
    workspace: Path, *, http_transport: httpx.AsyncBaseTransport | None = None
) -> dict[ToolGroup, list[AnyTool]]:
    return {
        ToolGroup.CALCULATOR: [calculator],
        ToolGroup.FILES: Workspace(workspace).tools(),
        ToolGroup.PYTHON: [PythonRunner(workspace).tool()],
        ToolGroup.HTTP: [HttpFetcher(transport=http_transport).tool()],
        ToolGroup.TIME: [current_time],
    }


def select_tools(
    names: Iterable[str],
    workspace: Path,
    *,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> list[AnyTool]:
    """Resolve group names (``files``) and tool names (``read_file``) to tools, in order."""
    catalog = builtin_tools(workspace, http_transport=http_transport)
    by_name = {tool.name: tool for tools in catalog.values() for tool in tools}
    selected: dict[str, AnyTool] = {}
    for raw in names:
        name = raw.strip()
        if not name:
            continue
        if name in ToolGroup:
            tools = catalog[ToolGroup(name)]
        elif name in by_name:
            tools = [by_name[name]]
        else:
            raise ValueError(
                f"unknown tool or group '{name}'; groups: {', '.join(ToolGroup)}; "
                f"tools: {', '.join(by_name)}"
            )
        selected.update((tool.name, tool) for tool in tools)
    return list(selected.values())
