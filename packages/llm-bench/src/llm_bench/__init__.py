"""Benchmark OpenAI-compatible LLM inference servers."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("llm-bench")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0"
