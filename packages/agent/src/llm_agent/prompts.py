"""Default system prompt, tuned for small local models: short, concrete, tool-first.

The chat template already injects the tool schemas and the call format, so the prompt
only has to say *when* to use tools and *when to stop*. Rules for tools that are not
enabled are left out: every token of system prompt is paid again on every step.
"""

from __future__ import annotations

from collections.abc import Collection

_INTRO = "You are a precise assistant that completes tasks by calling tools."

_TOOL_RULES: dict[str, str] = {
    "calculator": (
        "Use the calculator for every calculation, even simple ones. Never do arithmetic "
        "in your head."
    ),
    "read_file": ("File paths are relative to the workspace. Read a file before you describe it."),
    "run_python": "run_python returns only what the script prints, so print() the results.",
}

_GENERAL_RULES = (
    "Make independent tool calls together in one turn instead of one per turn.",
    "If a tool returns an error, fix the arguments and call it again.",
    "Base your answer only on tool results; do not invent values.",
    "When you have everything you need, reply with a short final answer and no tool call.",
)


def build_system_prompt(tool_names: Collection[str]) -> str:
    if not tool_names:
        return "You are a precise, concise assistant."
    rules = [rule for name, rule in _TOOL_RULES.items() if name in tool_names]
    rules.extend(_GENERAL_RULES)
    return "\n".join([_INTRO, "", *(f"- {rule}" for rule in rules)])
