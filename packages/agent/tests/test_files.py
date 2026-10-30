from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from llm_agent.tools.files import Workspace, WorkspaceError


@pytest.fixture
def files(workspace: Path) -> Workspace:
    return Workspace(workspace, max_read_bytes=100, max_write_bytes=100, max_entries=3)


def test_write_read_and_list(files: Workspace) -> None:
    assert files.write_file("notes/today.md", "# Plan\nship it\n") == (
        "Wrote 15 bytes to notes/today.md"
    )
    assert files.read_file("notes/today.md") == "# Plan\nship it\n"
    assert files.read_file("./notes/../notes/today.md") == "# Plan\nship it\n"
    (files.root / "empty.txt").touch()
    assert files.list_dir() == "notes/\nempty.txt (0 bytes)"
    assert files.list_dir("notes") == "today.md (15 bytes)"
    assert files.read_file("empty.txt") == "(empty file)"


@pytest.mark.parametrize("path", ["../secret.txt", "notes/../../secret.txt", "/etc/passwd"])
def test_paths_outside_the_workspace_are_refused(files: Workspace, path: str) -> None:
    (files.root.parent / "secret.txt").write_text("top secret")
    with pytest.raises(WorkspaceError, match="outside the workspace"):
        files.read_file(path)
    with pytest.raises(WorkspaceError, match="outside the workspace"):
        files.write_file(path, "pwned")
    assert (files.root.parent / "secret.txt").read_text() == "top secret"


def test_symlinks_cannot_escape(files: Workspace, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret")
    (files.root / "link").symlink_to(outside)
    (files.root / "file-link.txt").symlink_to(outside / "secret.txt")
    (files.root / "dangling").symlink_to(outside / "new.txt")

    attempts: list[Callable[[], str]] = [
        lambda: files.read_file("link/secret.txt"),
        lambda: files.read_file("file-link.txt"),
        lambda: files.list_dir("link"),
        lambda: files.write_file("file-link.txt", "pwned"),
        lambda: files.write_file("dangling", "pwned"),
    ]
    for attempt in attempts:
        with pytest.raises(WorkspaceError, match="outside the workspace"):
            attempt()
    assert (outside / "secret.txt").read_text() == "top secret"
    assert not (outside / "new.txt").exists()
    assert "link@ (symlink)" in files.list_dir()


def test_symlinks_inside_the_workspace_are_fine(files: Workspace) -> None:
    files.write_file("real.txt", "hello")
    (files.root / "alias.txt").symlink_to(files.root / "real.txt")
    assert files.read_file("alias.txt") == "hello"


def test_limits_and_text_only(files: Workspace) -> None:
    (files.root / "big.txt").write_text("x" * 101)
    (files.root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0")
    (files.root / "latin1.txt").write_bytes("café".encode("latin-1"))

    with pytest.raises(WorkspaceError, match="101 bytes; the read limit is 100"):
        files.read_file("big.txt")
    with pytest.raises(WorkspaceError, match="binary file"):
        files.read_file("image.png")
    with pytest.raises(WorkspaceError, match="not valid UTF-8"):
        files.read_file("latin1.txt")
    with pytest.raises(WorkspaceError, match="write limit is 100"):
        files.write_file("big2.txt", "x" * 101)
    with pytest.raises(WorkspaceError, match="does not exist"):
        files.read_file("missing.txt")
    with pytest.raises(WorkspaceError, match="is a directory"):
        files.write_file(".", "x")
    with pytest.raises(WorkspaceError, match="invalid path"):
        files.read_file("bad\0name")


def test_long_listings_are_capped(files: Workspace) -> None:
    for i in range(5):
        (files.root / f"f{i}.txt").touch()
    assert files.list_dir().splitlines()[-1] == "... and 2 more entries"


def test_tools_are_exposed_with_schemas(files: Workspace) -> None:
    tools = {tool.name: tool for tool in files.tools()}
    assert set(tools) == {"list_dir", "read_file", "write_file"}
    assert tools["write_file"].parameters["required"] == ["path", "content"]
    assert tools["list_dir"].parameters["properties"]["path"]["default"] == "."


def test_workspace_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        Workspace(tmp_path / "missing")
