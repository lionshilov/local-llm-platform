"""Evaluation harness for local LLMs: quality vs speed across engines and quantizations."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("llm-evals")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0"
