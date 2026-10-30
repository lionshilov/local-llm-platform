"""``current_time``: small models have no idea what day it is."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from llm_agent.tools.base import ToolError, tool


@tool
def current_time(timezone: str | None = None) -> str:
    """Return the current date and time (ISO 8601) and the day of the week.

    Args:
        timezone: IANA time zone such as "Europe/Berlin". Default: the local time zone.
    """
    try:
        now = datetime.now(ZoneInfo(timezone)) if timezone else datetime.now().astimezone()
    except (KeyError, ValueError, OSError) as exc:  # ZoneInfoNotFoundError is a KeyError
        raise ToolError(f"unknown time zone '{timezone}'; use an IANA name like 'UTC'") from exc
    return f"{now.isoformat(timespec='seconds')} ({now:%A})"
