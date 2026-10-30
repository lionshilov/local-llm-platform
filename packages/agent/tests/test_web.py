from __future__ import annotations

import httpx
import pytest
from llm_agent.tools import ToolError
from llm_agent.tools.web import HttpFetcher, html_to_text

PAGE = """<!doctype html><html><head><title>Docs</title><style>p {color: red}</style>
<script>alert("hi")</script></head><body><h1>Hello &amp; welcome</h1>
<p>First   paragraph.</p><ul><li>one</li><li>two</li></ul><noscript>enable js</noscript>
</body></html>"""


def handler(request: httpx.Request) -> httpx.Response:
    match request.url.path:
        case "/page":
            return httpx.Response(200, html=PAGE)
        case "/big":
            return httpx.Response(200, text="y" * 5000)
        case "/image":
            return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})
        case "/redirect":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:8080/props"})
        case _:
            return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def fetcher() -> HttpFetcher:
    # A public IP literal: no DNS lookup, and MockTransport means no network either.
    return HttpFetcher(max_bytes=1000, transport=httpx.MockTransport(handler))


def test_html_to_text() -> None:
    assert html_to_text(PAGE) == "Docs\nHello & welcome\nFirst paragraph.\n- one\n- two"


async def test_fetches_text_and_strips_html(fetcher: HttpFetcher) -> None:
    output = await fetcher.http_get("https://1.1.1.1/page")
    assert output.startswith("HTTP 200 text/html\n\nDocs\nHello & welcome")
    assert "alert" not in output
    assert "color" not in output


async def test_errors_status_codes_are_returned(fetcher: HttpFetcher) -> None:
    output = await fetcher.http_get("https://1.1.1.1/missing")
    assert output == 'HTTP 404 application/json\n\n{"error":"not found"}'


async def test_response_size_is_capped(fetcher: HttpFetcher) -> None:
    output = await fetcher.http_get("https://1.1.1.1/big")
    assert output.endswith("y" * 1000 + "\n[response truncated at 1,000 bytes]")


@pytest.mark.parametrize(
    ("url", "error"),
    [
        ("https://1.1.1.1/image", "unsupported content type 'image/png'"),
        ("file:///etc/passwd", "only http and https"),
        ("http://127.0.0.1:8080/props", "non-public address 127.0.0.1"),
        ("http://169.254.169.254/latest/meta-data/", "non-public address"),
        ("http://[::1]/", "non-public address ::1"),
        ("http://10.0.0.5/admin", "non-public address"),
        ("https://1.1.1.1/redirect", "non-public address 127.0.0.1"),
    ],
)
async def test_refused_requests(fetcher: HttpFetcher, url: str, error: str) -> None:
    with pytest.raises(ToolError, match=error):
        await fetcher.http_get(url)


async def test_private_addresses_can_be_allowed_explicitly() -> None:
    fetcher = HttpFetcher(allow_private=True, transport=httpx.MockTransport(handler))
    assert (await fetcher.http_get("http://127.0.0.1/page")).startswith("HTTP 200")
