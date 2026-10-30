from __future__ import annotations

import json
from pathlib import Path

import pytest
from llm_agent import cli, read_trace
from llm_agent.testing import ScriptedServer, answer, call_tools, tool_call
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def serve(monkeypatch: pytest.MonkeyPatch, *replies: dict[str, object]) -> ScriptedServer:
    server = ScriptedServer(list(replies))
    monkeypatch.setattr(cli, "_http_client", server.client)
    return server


BASE = ["run", "--base-url", "http://fake/v1", "--model", "fake-model"]


def test_run_renders_steps_and_writes_trace(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, workspace: Path, tmp_path: Path
) -> None:
    server = serve(
        monkeypatch,
        call_tools(
            tool_call("write_file", {"path": "a.txt", "content": "hello world"}),
            tool_call("calculator", {"expression": "2 ** 10"}),
            content="Writing the file and computing.",
        ),
        answer("Saved **a.txt**; 2^10 = 1024."),
    )
    trace = tmp_path / "trace.jsonl"
    args = [*BASE, "Save a note and compute 2^10", "--workspace", str(workspace)]
    result = runner.invoke(cli.app, [*args, "--trace", str(trace)])

    assert result.exit_code == 0, result.output
    assert (workspace / "a.txt").read_text() == "hello world"
    for expected in (
        "Step 1",
        "Writing the file and computing.",
        'write_file(path="a.txt", content="hello world")',
        "← calculator ✓ 1024",
        "Answer",
        "completed · 2 step(s) · 2 tool call(s)",
    ):
        assert expected in result.output
    assert [e.type for e in read_trace(trace)][-2:] == ["final_answer", "run_finished"]
    assert server.requests[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_json_output_and_options(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    server = serve(monkeypatch, answer("Paris"))
    result = runner.invoke(
        cli.app,
        [
            *BASE,
            "Capital of France?",
            "--json",
            "--tools",
            "calculator",
            "--think",
            "--thinking-switch",
            "effort",
            "--extra-body",
            '{"top_k": 20}',
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["answer"] == "Paris"
    body = server.requests[0]
    assert body["reasoning_effort"] == "medium"
    assert "chat_template_kwargs" not in body
    assert body["top_k"] == 20
    assert [t["function"]["name"] for t in body["tools"]] == ["calculator"]


def test_failed_run_exits_non_zero(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    serve(monkeypatch, *[call_tools(tool_call("calculator", {"expression": "1"}))] * 3)
    args = [*BASE, "loop", "--max-steps", "2", "--workspace", str(workspace)]
    result = runner.invoke(cli.app, args)

    assert result.exit_code == 1
    assert "Stopped: max_steps" in result.output


@pytest.mark.parametrize(
    ("option", "error"),
    [
        (["--tools", "calculator,shell"], "unknown tool or group 'shell'"),
        (["--extra-body", "[1]"], "must be a JSON object"),
        (["--extra-body", "{oops"], "not valid JSON"),
    ],
)
def test_bad_options_are_rejected(
    runner: CliRunner, workspace: Path, option: list[str], error: str
) -> None:
    result = runner.invoke(cli.app, [*BASE, "task", "--workspace", str(workspace), *option])
    assert result.exit_code == 2
    assert error in " ".join(result.output.split())


def test_tools_command(runner: CliRunner) -> None:
    table = runner.invoke(cli.app, ["tools"])
    assert table.exit_code == 0
    assert "run_python" in table.output
    assert "opt-in" in table.output

    schemas = json.loads(runner.invoke(cli.app, ["tools", "--json"]).output)
    calculator = next(s for s in schemas if s["function"]["name"] == "calculator")
    assert calculator["function"]["parameters"]["required"] == ["expression"]


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("llm-agent ")
