"""Tools: typed Python functions the model can call, plus the built-in set."""

from llm_agent.tools.base import AnyTool, Tool, ToolError, tool
from llm_agent.tools.builtin import DEFAULT_GROUPS, ToolGroup, builtin_tools, select_tools
from llm_agent.tools.calculator import calculator
from llm_agent.tools.clock import current_time
from llm_agent.tools.files import Workspace
from llm_agent.tools.python import PythonRunner
from llm_agent.tools.registry import ToolErrorKind, ToolRegistry, ToolResult
from llm_agent.tools.web import HttpFetcher

__all__ = [
    "DEFAULT_GROUPS",
    "AnyTool",
    "HttpFetcher",
    "PythonRunner",
    "Tool",
    "ToolError",
    "ToolErrorKind",
    "ToolGroup",
    "ToolRegistry",
    "ToolResult",
    "Workspace",
    "builtin_tools",
    "calculator",
    "current_time",
    "select_tools",
    "tool",
]
