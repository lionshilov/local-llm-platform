"""Filesystem tools confined to one workspace directory.

Every path from the model is joined to the workspace root and fully resolved, symlinks
included, before it is used. Anything that resolves outside the root is refused, which
blocks ``../`` traversal, absolute paths and symlinks pointing out of the workspace.
"""

from __future__ import annotations

from pathlib import Path

from llm_agent.tools.base import AnyTool, Tool, ToolError


class WorkspaceError(ToolError):
    pass


class Workspace:
    def __init__(
        self,
        root: Path,
        *,
        max_read_bytes: int = 256_000,
        max_write_bytes: int = 1_000_000,
        max_entries: int = 200,
    ) -> None:
        self.root = root.expanduser().resolve()
        if not self.root.is_dir():
            raise ValueError(f"workspace '{root}' is not a directory")
        self.max_read_bytes = max_read_bytes
        self.max_write_bytes = max_write_bytes
        self.max_entries = max_entries

    def resolve(self, path: str) -> Path:
        """Map a model-supplied path to a real path inside the workspace, or refuse."""
        try:
            candidate = (self.root / path).resolve()
        except (OSError, RuntimeError, ValueError) as exc:  # symlink loops, NUL bytes
            raise WorkspaceError(f"invalid path '{path}': {exc}") from exc
        if not candidate.is_relative_to(self.root):
            raise WorkspaceError(
                f"'{path}' is outside the workspace; use a path relative to the workspace root"
            )
        return candidate

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def list_dir(self, path: str = ".") -> str:
        """List a workspace directory. Sub-directories end with '/', files show their size.

        Args:
            path: Directory relative to the workspace root; "." is the root itself.
        """
        directory = self.resolve(path)
        if not directory.is_dir():
            raise WorkspaceError(f"'{path}' is not a directory")
        entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = []
        for entry in entries[: self.max_entries]:
            if entry.is_symlink():
                lines.append(f"{entry.name}@ (symlink)")
            elif entry.is_dir():
                lines.append(f"{entry.name}/")
            else:
                lines.append(f"{entry.name} ({entry.stat().st_size:,} bytes)")
        if len(entries) > self.max_entries:
            lines.append(f"... and {len(entries) - self.max_entries} more entries")
        return "\n".join(lines) or "(empty directory)"

    def read_file(self, path: str) -> str:
        """Read a UTF-8 text file from the workspace.

        Args:
            path: File path relative to the workspace root.
        """
        file = self.resolve(path)
        if not file.is_file():
            raise WorkspaceError(f"'{path}' does not exist or is not a file")
        size = file.stat().st_size
        if size > self.max_read_bytes:
            raise WorkspaceError(
                f"'{path}' is {size:,} bytes; the read limit is {self.max_read_bytes:,} bytes"
            )
        with file.open("rb") as fh:
            data = fh.read(self.max_read_bytes)
        if b"\0" in data:
            raise WorkspaceError(f"'{path}' looks like a binary file; only text can be read")
        try:
            text = data.decode()
        except UnicodeDecodeError as exc:
            raise WorkspaceError(f"'{path}' is not valid UTF-8 text") from exc
        return text or "(empty file)"

    def write_file(self, path: str, content: str) -> str:
        """Create or overwrite a UTF-8 text file in the workspace; missing folders are created.

        Args:
            path: File path relative to the workspace root, e.g. "notes/summary.md".
            content: The complete new content of the file.
        """
        data = content.encode()
        if len(data) > self.max_write_bytes:
            raise WorkspaceError(
                f"content is {len(data):,} bytes; the write limit is {self.max_write_bytes:,}"
            )
        file = self.resolve(path)
        if file == self.root or file.is_dir():
            raise WorkspaceError(f"'{path}' is a directory")
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        return f"Wrote {len(data):,} bytes to {self.relative(file)}"

    def tools(self) -> list[AnyTool]:
        return [Tool(self.list_dir), Tool(self.read_file), Tool(self.write_file)]
