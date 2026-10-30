"""Tool-calling agent harness for local LLMs, built from scratch."""

from importlib.metadata import PackageNotFoundError, version

from llm_agent.agent import Agent, RunResult, Step
from llm_agent.config import AgentLimits, ClientConfig, ThinkingSwitch
from llm_agent.events import Event, JsonlTrace, RunStatus, read_trace
from llm_agent.tools import Tool, ToolError, tool

try:
    __version__ = version("llm-agent")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0"

__all__ = [
    "Agent",
    "AgentLimits",
    "ClientConfig",
    "Event",
    "JsonlTrace",
    "RunResult",
    "RunStatus",
    "Step",
    "ThinkingSwitch",
    "Tool",
    "ToolError",
    "__version__",
    "read_trace",
    "tool",
]
