# syntax=docker/dockerfile:1
# llm-gateway + chat UI. Build from the repository root:
#   docker build -f deploy/gateway.Dockerfile -t llm-gateway .

ARG NODE_VERSION=22.23.4
ARG PYTHON_VERSION=3.12.16
ARG UV_VERSION=0.11.29

# --- 1. Chat UI: static files, identical on every platform, so build natively ---------
FROM --platform=$BUILDPLATFORM node:${NODE_VERSION}-alpine3.24 AS ui
WORKDIR /src/ui
COPY ui/package.json ui/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

# --- 2. Python virtualenv with only the gateway and its locked dependencies -----------
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-slim-trixie AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src

# Third-party dependencies first: this layer only rebuilds when uv.lock changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=services/gateway/pyproject.toml,target=services/gateway/pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace --package llm-gateway

# Then the gateway itself, installed as a regular (non-editable) package.
COPY pyproject.toml uv.lock ./
COPY services/gateway ./services/gateway
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package llm-gateway

# --- 3. Runtime: no build tools, no uv, no sources, non-root --------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS runtime

LABEL org.opencontainers.image.title="llm-gateway" \
      org.opencontainers.image.description="OpenAI-compatible gateway for local LLM engines, with Prometheus metrics and a chat UI" \
      org.opencontainers.image.source="https://github.com/lionshilov/local-llm-platform" \
      org.opencontainers.image.licenses="Apache-2.0"

RUN groupadd --gid 10001 gateway \
 && useradd --uid 10001 --gid gateway --home-dir /app --no-create-home \
      --shell /usr/sbin/nologin gateway

# Owned by root and read-only for the service user: the process cannot modify its code.
COPY --from=builder /app/.venv /app/.venv
COPY --from=ui /src/ui/dist /app/ui/dist
# Default config for `docker run` on Docker Desktop; compose mounts its own copy here.
COPY deploy/gateway.docker.yaml /config/gateway.yaml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["llm-gateway", "--host", "0.0.0.0", "--port", "8000", \
     "--config", "/config/gateway.yaml", "--ui-dir", "/app/ui/dist"]
