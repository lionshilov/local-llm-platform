"""Test-wide settings shared by every package in the workspace.

Typer and Rich decide at import time whether to emit colours and terminal formatting,
based on variables such as GITHUB_ACTIONS and FORCE_COLOR. CLI tests assert on plain
text, so make the output identical locally and in CI before any CLI module is imported.
"""

import os

for variable in ("FORCE_COLOR", "PY_COLORS", "GITHUB_ACTIONS"):
    os.environ.pop(variable, None)
os.environ["NO_COLOR"] = "1"
os.environ["_TYPER_FORCE_DISABLE_TERMINAL"] = "1"
os.environ["COLUMNS"] = "200"
