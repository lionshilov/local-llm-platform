from __future__ import annotations

import re
from pathlib import Path

import pytest
from llm_agent.prompts import build_system_prompt
from llm_agent.tools import DEFAULT_GROUPS, ToolError, current_time, select_tools


def names(spec: list[str], workspace: Path) -> list[str]:
    return [tool.name for tool in select_tools(spec, workspace)]


def test_groups_and_single_tools_can_be_selected(workspace: Path) -> None:
    assert names(list(DEFAULT_GROUPS), workspace) == [
        "calculator",
        "list_dir",
        "read_file",
        "write_file",
        "current_time",
    ]
    assert names(["read_file", " python ", "", "files"], workspace) == [
        "read_file",
        "run_python",
        "list_dir",
        "write_file",
    ]


def test_unknown_names_are_rejected(workspace: Path) -> None:
    with pytest.raises(ValueError, match="unknown tool or group 'shell'"):
        select_tools(["shell"], workspace)


def test_risky_tools_are_opt_in() -> None:
    assert "python" not in DEFAULT_GROUPS
    assert "http" not in DEFAULT_GROUPS


def test_current_time() -> None:
    assert re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00 \(\w+day\)", current_time(timezone="UTC")
    )
    assert "T" in current_time()
    with pytest.raises(ToolError, match="unknown time zone 'Mars/Base'"):
        current_time(timezone="Mars/Base")


def test_system_prompt_only_mentions_enabled_tools() -> None:
    with_calc = build_system_prompt(["calculator"])
    assert "calculator" in with_calc
    assert "print()" not in with_calc
    assert "print()" in build_system_prompt(["run_python"])
    assert "tool" not in build_system_prompt([])
