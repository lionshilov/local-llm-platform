"""``llm-gateway``: run the gateway (and the built chat UI) with uvicorn."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn

from llm_gateway.app import create_app
from llm_gateway.config import GatewayConfig

_PROBE_PATHS = ('"GET /metrics ', '"GET /healthz ')


class _HideProbes(logging.Filter):
    """Prometheus scrapes and health checks every few seconds would drown the access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(path in message for path in _PROBE_PATHS)


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
    config = uvicorn.Config(app, host=args.host, port=args.port)  # configures logging
    logging.getLogger("uvicorn.access").addFilter(_HideProbes())
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
