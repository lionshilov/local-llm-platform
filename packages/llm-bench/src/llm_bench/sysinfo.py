"""Describe the machine and the servers so results are reproducible and comparable.

Deliberately excludes hostname, username and paths: result files are committed publicly.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from llm_bench.config import Engine


def system_info() -> dict[str, Any]:
    return {
        "os": platform.platform(terse=True),
        "machine": platform.machine(),
        "cpu": _cpu_name(),
        "memory_gb": _memory_gb(),
        "python": platform.python_version(),
    }


def _cpu_name() -> str:
    if sys.platform == "darwin":
        try:
            out = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def _memory_gb() -> float | None:
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 1)
    except (ValueError, OSError, AttributeError):
        return None


class EngineProbe(BaseModel):
    available: bool
    models: list[str] = []
    server: str | None = None
    error: str | None = None


async def probe_engine(client: httpx.AsyncClient, engine: Engine) -> EngineProbe:
    """Check that the endpoint is up and try to identify the server build."""
    try:
        response = await client.get(f"{engine.base_url}/models", timeout=5)
        response.raise_for_status()
        models = [m.get("id", "?") for m in response.json().get("data", [])]
    except (httpx.HTTPError, ValueError) as exc:
        return EngineProbe(available=False, error=f"{type(exc).__name__}: {exc}")
    return EngineProbe(available=True, models=models, server=await _server_version(client, engine))


async def _server_version(client: httpx.AsyncClient, engine: Engine) -> str | None:
    root = engine.base_url.removesuffix("/v1")
    try:
        ollama = await client.get(f"{root}/api/version", timeout=3)
        if ollama.status_code == httpx.codes.OK and "version" in ollama.json():
            return f"ollama {ollama.json()['version']}"
        llamacpp = await client.get(f"{root}/props", timeout=3)
        if llamacpp.status_code == httpx.codes.OK and "build_info" in llamacpp.json():
            return f"llama.cpp {llamacpp.json()['build_info']}"
    except (httpx.HTTPError, ValueError):
        pass
    return None
