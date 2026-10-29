"""OpenAI-compatible gateway in front of local LLM engines."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("llm-gateway")
except PackageNotFoundError:  # running from a source checkout without install
    __version__ = "0.0.0"
