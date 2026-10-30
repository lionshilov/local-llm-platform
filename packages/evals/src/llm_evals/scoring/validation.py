"""Typed facade over ``jsonschema`` (JSON Schema draft 2020-12).

``jsonschema`` ships without type information; this is the only module that touches it, so
the rest of the package stays fully typed.
"""

from __future__ import annotations

from typing import Any

import jsonschema
from pydantic import JsonValue


def check_schema(schema: dict[str, Any]) -> None:
    """Raise ``ValueError`` if ``schema`` is not a valid draft 2020-12 JSON Schema."""
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise ValueError(f"invalid JSON Schema: {exc.message}") from exc


def schema_errors(instance: JsonValue, schema: dict[str, Any]) -> list[str]:
    """Human-readable violations, most relevant first; empty if ``instance`` is valid."""
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=jsonschema.exceptions.relevance)
    messages: list[str] = []
    for error in errors:
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        messages.append(f"{location}: {error.message}")
    return messages
