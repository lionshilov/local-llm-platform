"""``run_python``: execute a script in a separate interpreter. This is NOT a security sandbox.

What is limited: wall-clock time (the whole process group is killed), output size, the
environment (nothing is inherited, so no API keys or tokens leak in), the working
directory (the workspace) and interpreter state (``-I``: no user site-packages, no
``PYTHON*`` variables). What is not: the code runs as your user, so it can read and write
any file you can, open network connections and use all CPU and memory until it is killed.
Only enable it for trusted tasks; for untrusted code, run the agent inside a container or
a gVisor / Firecracker sandbox.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
from pathlib import Path

from llm_agent.tools.base import AnyTool, Tool, ToolError

_READ_CHUNK = 64 * 1024


async def _drain(stream: asyncio.StreamReader | None, limit: int) -> tuple[str, int]:
    """Read ``stream`` to EOF keeping at most ``limit`` bytes; return (text, total bytes)."""
    kept = bytearray()
    total = 0
    while stream is not None and (chunk := await stream.read(_READ_CHUNK)):
        total += len(chunk)
        if len(kept) < limit:
            kept += chunk[: limit - len(kept)]
    return kept.decode(errors="replace"), total


def _kill_process_group(process: asyncio.subprocess.Process) -> None:
    # Also reaps anything the script started in the background.
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGKILL)


def _section(label: str, text: str, total: int, limit: int) -> str:
    note = f"\n[... truncated {total - limit:,} bytes]" if total > limit else ""
    return f"--- {label} ---\n{text.rstrip()}{note}"


class PythonRunner:
    def __init__(
        self, workspace: Path, *, timeout_s: float = 10.0, max_output_bytes: int = 4000
    ) -> None:
        self.workspace = workspace.resolve()
        self.timeout_s = timeout_s
        self.max_output_bytes = max_output_bytes

    def _environment(self) -> dict[str, str]:
        return {"PATH": os.defpath, "HOME": str(self.workspace), "LANG": "C.UTF-8"}

    async def run_python(self, code: str) -> str:
        """Run a Python 3 script in a fresh process; returns its stdout and stderr.

        The working directory is the workspace. Only printed output is returned, so
        print() every value you need.

        Args:
            code: A complete Python script.
        """
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",  # isolated: ignore PYTHON* env vars, user site-packages, cwd on sys.path
            "-B",  # no .pyc files in the workspace
            "-X",
            "utf8",
            "-c",
            code,
            cwd=self.workspace,
            env=self._environment(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # own process group, so a timeout kills its children too
        )
        readers = asyncio.gather(
            _drain(process.stdout, self.max_output_bytes),
            _drain(process.stderr, self.max_output_bytes),
        )
        timed_out = False
        try:
            await asyncio.wait_for(process.wait(), self.timeout_s)
        except TimeoutError:
            timed_out = True
        finally:
            _kill_process_group(process)
            await process.wait()
        (out, out_total), (err, err_total) = await readers

        sections = [
            _section(label, text, total, self.max_output_bytes)
            for label, text, total in (("stdout", out, out_total), ("stderr", err, err_total))
            if total
        ]
        output = "\n".join(sections) or "(no output: use print() to show results)"
        if timed_out:
            raise ToolError(f"timed out after {self.timeout_s:g} s; process killed\n{output}")
        if process.returncode != 0:
            raise ToolError(f"exit code {process.returncode}\n{output}")
        return output

    def tool(self) -> AnyTool:
        return Tool(self.run_python)
