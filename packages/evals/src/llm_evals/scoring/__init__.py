"""Programmatic scorers: deterministic functions from a model reply to a verdict.

Every scorer must be total: any string a model can produce yields a ``Score``, never an
exception, because a crash 20 minutes into a run would throw away every result so far.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, JsonValue


class Score(BaseModel):
    passed: bool
    extracted: JsonValue = Field(
        default=None, description="What the scorer read out of the reply, for debugging."
    )
    reason: str | None = Field(default=None, description="Why the item failed.")
    checks: dict[str, bool] = Field(
        default_factory=dict,
        description="Named sub-checks (e.g. schema_valid, function) for the breakdown table.",
    )
