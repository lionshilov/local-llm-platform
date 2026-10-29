"""``llm-gateway``: run the gateway (and the built chat UI) with uvicorn."""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from llm_gateway.app import create_app
from llm_gateway.config import GatewayConfig


def main() -> None:
    parser = argparse.ArgumentParser(prog="llm-gateway", description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/gateway.yaml"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--ui-dir", type=Path, default=Path("ui/dist"), help="Built chat UI to serve at /."
    )
    args = parser.parse_args()

    app = create_app(GatewayConfig.load(args.config), ui_dir=args.ui_dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
