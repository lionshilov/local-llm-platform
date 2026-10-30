"""Command line interface: ``llm-agent run "task"`` and ``llm-agent tools``."""

from __future__ import annotations

import asyncio
import contextlib
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer
from pydantic import SecretStr
from rich.console import Console
from rich.table import Table
from rich.text import Text

from llm_agent import __version__
from llm_agent.agent import Agent, RunResult
from llm_agent.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AgentLimits,
    ClientConfig,
    ThinkingSwitch,
)
from llm_agent.events import EventHandler, JsonlTrace
from llm_agent.render import RichRenderer
from llm_agent.tools import DEFAULT_GROUPS, AnyTool, ToolGroup, builtin_tools, select_tools

app = typer.Typer(
    help="Tool-calling agent for local LLMs behind any OpenAI-compatible API.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))


def _json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"not valid JSON: {exc}", param_hint="--extra-body") from exc
    if not isinstance(value, dict):
        raise typer.BadParameter("must be a JSON object", param_hint="--extra-body")
    return value


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="What the agent should do.")],
    base_url: Annotated[
        str, typer.Option(envvar="LLM_AGENT_BASE_URL", help="OpenAI-compatible base URL.")
    ] = DEFAULT_BASE_URL,
    model: Annotated[
        str, typer.Option("--model", "-m", envvar="LLM_AGENT_MODEL", help="Model id.")
    ] = DEFAULT_MODEL,
    api_key: Annotated[
        str | None,
        typer.Option(envvar="LLM_AGENT_API_KEY", show_default=False, help="Bearer token."),
    ] = None,
    tools: Annotated[
        str,
        typer.Option(
            "--tools",
            "-t",
            help=f"Comma-separated groups or tool names: {', '.join(ToolGroup)}. "
            "python and http are off unless listed.",
        ),
    ] = ",".join(DEFAULT_GROUPS),
    workspace: Annotated[
        Path | None,
        typer.Option(
            file_okay=False,
            help="Directory the file and python tools are confined to. Default: a new temp dir.",
        ),
    ] = None,
    max_steps: Annotated[int, typer.Option(min=1, help="Model calls per run.")] = 10,
    tool_timeout: Annotated[float, typer.Option(min=0.1, help="Seconds per tool call.")] = 30.0,
    time_budget: Annotated[
        float, typer.Option(min=1.0, help="Wall-clock seconds for the whole run.")
    ] = 300.0,
    think: Annotated[
        bool, typer.Option("--think/--no-think", help="Let reasoning models think first.")
    ] = False,
    thinking_switch: Annotated[
        ThinkingSwitch, typer.Option(help="Which request field(s) carry the thinking switch.")
    ] = ThinkingSwitch.PORTABLE,
    temperature: Annotated[float, typer.Option(min=0.0, max=2.0)] = 0.0,
    max_tokens: Annotated[int, typer.Option(min=1, help="Generation cap per step.")] = 2048,
    extra_body: Annotated[
        str | None,
        typer.Option(help="JSON merged into every request body, e.g. '{\"top_k\": 20}'."),
    ] = None,
    system_prompt: Annotated[
        Path | None,
        typer.Option(exists=True, dir_okay=False, help="File replacing the default prompt."),
    ] = None,
    trace: Annotated[
        Path | None, typer.Option(dir_okay=False, help="Append every event to this JSONL file.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the full result as JSON instead of live output.")
    ] = False,
) -> None:
    """Run the agent on TASK until it answers or a limit is hit (exit code 1 if it fails)."""
    root = workspace or Path(tempfile.mkdtemp(prefix="llm-agent-"))
    root.mkdir(parents=True, exist_ok=True)
    try:
        selected = select_tools(tools.split(","), root)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--tools") from exc

    config = ClientConfig(
        base_url=base_url,
        model=model,
        api_key=SecretStr(api_key) if api_key else None,
        temperature=temperature,
        max_tokens=max_tokens,
        think=think,
        thinking_switch=thinking_switch,
        extra_body=_json_object(extra_body),
    )
    limits = AgentLimits(
        max_steps=max_steps, tool_timeout_s=tool_timeout, time_budget_s=time_budget
    )
    prompt = system_prompt.read_text() if system_prompt else None

    if not json_output:
        console.print(Text(f"workspace: {root.resolve()}", style="dim"))
    result = asyncio.run(_run_agent(task, config, selected, limits, prompt, trace, json_output))
    if json_output:
        typer.echo(result.model_dump_json(indent=2))
    if not result.ok:
        raise typer.Exit(1)


async def _run_agent(
    task: str,
    config: ClientConfig,
    tools: Sequence[AnyTool],
    limits: AgentLimits,
    system_prompt: str | None,
    trace: Path | None,
    quiet: bool,
) -> RunResult:
    handlers: list[EventHandler] = []
    with contextlib.ExitStack() as stack:
        if trace is not None:
            handlers.append(stack.enter_context(JsonlTrace(trace)))
        if not quiet:
            status = stack.enter_context(console.status("Starting…"))
            handlers.append(RichRenderer(console, status=status))
        async with _http_client() as http:
            agent = Agent(
                config,
                tools,
                limits=limits,
                system_prompt=system_prompt,
                http_client=http,
                on_event=handlers,
            )
            return await agent.run(task)


def _signature(parameters: dict[str, Any]) -> str:
    """Summarize a JSON schema's properties as ``name: type = default, ...``."""
    parts = []
    for name, schema in parameters.get("properties", {}).items():
        variants = schema.get("anyOf", [schema])
        kind = " | ".join(str(v.get("type", "any")) for v in variants)
        default = f" = {json.dumps(schema['default'])}" if "default" in schema else ""
        parts.append(f"{name}: {kind}{default}")
    return ", ".join(parts)


@app.command("tools")
def list_tools(
    json_output: Annotated[
        bool, typer.Option("--json", help="Print the exact `tools` array sent to the model.")
    ] = False,
) -> None:
    """List the built-in tools with their groups and JSON schemas."""
    catalog = builtin_tools(Path.cwd())  # schemas do not depend on the workspace
    if json_output:
        schemas = [tool.schema() for group in catalog.values() for tool in group]
        typer.echo(json.dumps(schemas, indent=2))
        return

    table = Table(header_style="bold cyan")
    for column in ("Tool", "Group", "Default", "Parameters", "Description"):
        table.add_column(column)
    for group, group_tools in catalog.items():
        enabled = "[green]on[/]" if group in DEFAULT_GROUPS else "[yellow]opt-in[/]"
        for tool in group_tools:
            summary = tool.description.split("\n\n")[0]
            table.add_row(tool.name, group, enabled, _signature(tool.parameters), summary)
    console.print(table)
    console.print("[dim]Full JSON schemas: llm-agent tools --json[/]")


@app.callback(invoke_without_command=True)
def _version(
    version: Annotated[bool, typer.Option("--version", help="Show version and exit.")] = False,
) -> None:
    if version:
        typer.echo(f"llm-agent {__version__}")
        raise typer.Exit
