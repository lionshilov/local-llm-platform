"""Minimal Google-style docstring parser: a summary plus per-argument descriptions."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field

_SECTION = re.compile(r"^(\w+(?: \w+)?):\s*$")
_ARG_SECTIONS = frozenset({"Args", "Arguments", "Parameters"})
_KNOWN_SECTIONS = _ARG_SECTIONS | {
    "Returns",
    "Return",
    "Yields",
    "Raises",
    "Example",
    "Examples",
    "Note",
    "Notes",
    "See Also",
}
_ARG = re.compile(r"^\*{0,2}(\w+)\s*(?:\([^)]*\))?\s*:\s*(.*)$")


@dataclass(frozen=True)
class Docstring:
    summary: str
    args: dict[str, str] = field(default_factory=dict)


def _join_paragraphs(lines: list[str]) -> str:
    paragraphs = "\n".join(lines).strip().split("\n\n")
    return "\n\n".join(" ".join(p.split()) for p in paragraphs if p.strip())


def parse_docstring(doc: str | None) -> Docstring:
    """Split a docstring into its summary and its ``Args:`` descriptions."""
    summary: list[str] = []
    args: dict[str, list[str]] = {}
    section: str | None = None
    arg_indent: int | None = None
    current: str | None = None

    for line in inspect.cleandoc(doc or "").splitlines():
        stripped = line.strip()
        header = _SECTION.match(line)
        if header and header.group(1) in _KNOWN_SECTIONS:
            section, arg_indent, current = header.group(1), None, None
            continue
        if section is None:
            summary.append(line)
            continue
        if section not in _ARG_SECTIONS or not stripped:
            continue

        indent = len(line) - len(line.lstrip())
        if arg_indent is None:
            arg_indent = indent
        match = _ARG.match(stripped)
        if match and indent == arg_indent:
            current = match.group(1)
            args[current] = [match.group(2)]
        elif current is not None and indent > arg_indent:
            args[current].append(stripped)

    return Docstring(
        summary=_join_paragraphs(summary),
        args={name: " ".join(" ".join(parts).split()) for name, parts in args.items()},
    )
