"""``http_get``: fetch a page as text. Off by default because it gives the model the network.

Guards: http(s) only, a timeout, a response size cap, text content types only, and no
private, loopback or link-local destinations, checked on every redirect hop. Without that
last one a prompt injection in a fetched page could make the agent probe your LAN, the
local inference server or a cloud metadata endpoint (classic SSRF).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from html.parser import HTMLParser

import httpx

from llm_agent.tools.base import AnyTool, Tool, ToolError

_USER_AGENT = "llm-agent (+https://github.com/lionshilov/local-llm-platform)"
_TEXT_TYPES = frozenset({"application/json", "application/xml", "application/javascript"})
_SKIP_TAGS = frozenset({"script", "style", "noscript", "template", "svg"})
_BLOCK_TAGS = frozenset(
    {"p", "div", "br", "li", "tr", "section", "article", "header", "footer", "title"}
    | {"h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote", "table", "ul", "ol"}
)


class _TextExtractor(HTMLParser):
    """HTML to readable plain text: drops scripts and styles, keeps block structure."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skipping += 1
        elif tag == "li":
            self._parts.append("\n- ")
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skipping = max(0, self._skipping - 1)
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._parts.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._parts).splitlines())
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()


def _is_text(mime: str) -> bool:
    return (
        not mime
        or mime.startswith("text/")
        or mime in _TEXT_TYPES
        or mime.endswith(("+json", "+xml"))
    )


class HttpFetcher:
    def __init__(
        self,
        *,
        timeout_s: float = 10.0,
        max_bytes: int = 500_000,
        allow_private: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_bytes = max_bytes
        self.allow_private = allow_private
        self.transport = transport

    async def _check_destination(self, request: httpx.Request) -> None:
        """Runs before every request, redirects included."""
        url = request.url
        if url.scheme not in ("http", "https"):
            raise ToolError(f"only http and https URLs are allowed, not '{url.scheme}'")
        if self.allow_private:
            return
        try:
            addresses = [ipaddress.ip_address(url.host)]
        except ValueError:
            try:
                port = url.port or (443 if url.scheme == "https" else 80)
                infos = await asyncio.get_running_loop().getaddrinfo(
                    url.host, port, type=socket.SOCK_STREAM
                )
            except OSError as exc:
                raise ToolError(f"cannot resolve host '{url.host}': {exc}") from exc
            addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
        for address in addresses:
            if not address.is_global:
                raise ToolError(
                    f"refusing to fetch '{url.host}': it resolves to non-public address {address}"
                )

    async def http_get(self, url: str) -> str:
        """Fetch a web page or API response over HTTP(S) and return it as plain text.

        Args:
            url: Absolute URL, e.g. "https://example.com/page".
        """
        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=self.timeout_s,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": _USER_AGENT},
            event_hooks={"request": [self._check_destination]},
        ) as client:
            try:
                async with client.stream("GET", url) as response:
                    mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if not _is_text(mime):
                        raise ToolError(f"unsupported content type '{mime}': only text is returned")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > self.max_bytes:
                            break
            except httpx.HTTPError as exc:
                raise ToolError(f"request failed: {type(exc).__name__}: {exc}") from exc

        truncated = len(body) > self.max_bytes
        text = bytes(body[: self.max_bytes]).decode(response.encoding or "utf-8", errors="replace")
        if "html" in mime:
            text = html_to_text(text)
        note = f"\n[response truncated at {self.max_bytes:,} bytes]" if truncated else ""
        return f"HTTP {response.status_code} {mime or 'unknown type'}\n\n{text}{note}"

    def tool(self) -> AnyTool:
        return Tool(self.http_get)
