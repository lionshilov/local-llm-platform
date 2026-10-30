"""An OpenAI-compatible backend that answers instantly, to isolate the gateway's own cost.

Streams a fixed number of tokens with no model behind it, so any latency difference
between calling it directly and calling it through the gateway is the gateway.

    uv run python benchmarks/tools/instant_backend.py --port 9100 --tokens 64
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse


def create_app(tokens: int, delay_s: float) -> FastAPI:
    app = FastAPI()

    @app.get("/v1/models")
    async def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "instant"}]}

    @app.post("/v1/chat/completions")
    async def chat(request: Request) -> StreamingResponse:
        body = await request.json()
        count = min(tokens, int(body.get("max_tokens") or tokens))

        async def stream() -> AsyncIterator[bytes]:
            for i in range(count):
                chunk = {"choices": [{"index": 0, "delta": {"content": f"t{i} "}}]}
                yield f"data: {json.dumps(chunk)}\n\n".encode()
                if delay_s:
                    await asyncio.sleep(delay_s)
            usage = {"prompt_tokens": 50, "completion_tokens": count}
            yield f"data: {json.dumps({'choices': [], 'usage': usage})}\n\n".encode()
            yield b"data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--tokens", type=int, default=64)
    parser.add_argument("--delay-ms", type=float, default=0.0, help="Pause between tokens.")
    args = parser.parse_args()
    app = create_app(args.tokens, args.delay_ms / 1000)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
