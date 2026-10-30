from __future__ import annotations

import time
from pathlib import Path

import pytest
from llm_agent.tools import ToolError
from llm_agent.tools.python import PythonRunner


@pytest.fixture
def runner(workspace: Path) -> PythonRunner:
    return PythonRunner(workspace, timeout_s=30, max_output_bytes=200)


async def test_runs_in_the_workspace_and_returns_output(runner: PythonRunner) -> None:
    (runner.workspace / "data.txt").write_text("3 4 5")
    code = "import os, sys\nprint(sum(map(int, open('data.txt').read().split())))\n"
    code += "print('warn', file=sys.stderr)\nprint(os.getcwd())"
    output = await runner.run_python(code)

    assert output.startswith("--- stdout ---\n12\n")
    assert str(runner.workspace) in output
    assert output.endswith("--- stderr ---\nwarn")


async def test_environment_does_not_leak_secrets(
    runner: PythonRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    monkeypatch.setenv("PYTHONPATH", "/evil")
    output = await runner.run_python(
        "import os, sys; print(sorted(os.environ), sys.flags.isolated)"
    )

    assert "OPENAI_API_KEY" not in output
    assert "PYTHONPATH" not in output
    assert "['HOME', 'LANG', 'PATH'" in output
    assert output.rstrip().endswith("1")


async def test_timeout_kills_the_process_and_keeps_partial_output(workspace: Path) -> None:
    runner = PythonRunner(workspace, timeout_s=1)
    started = time.perf_counter()
    code = "import time\nprint('started', flush=True)\nwhile True: time.sleep(0.01)"
    with pytest.raises(ToolError, match=r"timed out after 1 s; process killed") as info:
        await runner.run_python(code)

    assert time.perf_counter() - started < 5
    assert "started" in str(info.value)


async def test_output_is_truncated(runner: PythonRunner) -> None:
    output = await runner.run_python("print('x' * 100_000)")
    assert output == f"--- stdout ---\n{'x' * 200}\n[... truncated 99,801 bytes]"


async def test_failures_report_exit_code_and_traceback(runner: PythonRunner) -> None:
    with pytest.raises(ToolError, match="exit code 1") as info:
        await runner.run_python("1 / 0")
    assert "ZeroDivisionError" in str(info.value)


async def test_silent_scripts_get_a_hint(runner: PythonRunner) -> None:
    assert "use print()" in await runner.run_python("x = 1")
