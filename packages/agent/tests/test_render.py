from __future__ import annotations

from datetime import UTC, datetime

from llm_agent.events import RunFailed, RunStarted, RunStatus, ToolReturned
from llm_agent.render import RichRenderer, format_arguments, preview
from rich.console import Console


def test_untrusted_text_is_never_parsed_as_markup() -> None:
    console = Console(record=True, width=100)
    render = RichRenderer(console)
    render(
        RunStarted(
            task="sum a[0] and [bold]b[/bold]",
            model="m",
            base_url="http://x/v1",
            tools=[],
            started_at=datetime.now(UTC),
        )
    )
    render(
        ToolReturned(
            step=1, call_id="c", name="t", ok=False, output="[/oops]", error=None, latency_s=0
        )
    )
    render(RunFailed(step=1, status=RunStatus.MODEL_ERROR, message="HTTP 500: [/broken]"))

    text = console.export_text()
    assert "sum a[0] and [bold]b[/bold]" in text
    assert "[/oops]" in text
    assert "HTTP 500: [/broken]" in text


def test_argument_and_output_previews() -> None:
    assert format_arguments('{"path": "a.md", "n": 2}') == 'path="a.md", n=2'
    assert format_arguments('{"code": "x"') == '{"code": "x"'
    assert format_arguments('{"text": "' + "y" * 100 + '"}', value_limit=10) == 'text="yyyyyyyy…'
    assert preview("one\n\n two\nthree\nfour\nfive", max_lines=3) == (
        "one\n two\nthree\n… 2 more line(s)"
    )
