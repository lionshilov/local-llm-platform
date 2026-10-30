"""Prometheus metrics, named and bucketed for LLM serving SLOs."""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    generate_latest,
)

_TTFT_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 2.5, 5.0, 10.0, 30.0, 60.0)
_TPOT_BUCKETS = (0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.075, 0.1, 0.25, 0.5)


class GatewayMetrics:
    """One registry per app instance, so tests and multiple apps never share state."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        # CPU, memory, open fds, GC (process metrics are reported on Linux only).
        ProcessCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        GCCollector(registry=self.registry)
        labels = ["backend"]
        self.requests = Counter(
            "llm_gateway_requests",
            "Chat completion requests by backend and outcome.",
            [*labels, "outcome"],
            registry=self.registry,
        )
        self.in_flight = Gauge(
            "llm_gateway_in_flight_requests",
            "Requests currently being served.",
            labels,
            registry=self.registry,
        )
        self.ttft = Histogram(
            "llm_gateway_time_to_first_token_seconds",
            "Time from receiving a streaming request to relaying its first token.",
            labels,
            buckets=_TTFT_BUCKETS,
            registry=self.registry,
        )
        self.tpot = Histogram(
            "llm_gateway_time_per_output_token_seconds",
            "Average time per output token after the first, per request.",
            labels,
            buckets=_TPOT_BUCKETS,
            registry=self.registry,
        )
        self.prompt_tokens = Counter(
            "llm_gateway_prompt_tokens",
            "Prompt tokens reported by upstream usage.",
            labels,
            registry=self.registry,
        )
        self.queue_depth = Gauge(
            "llm_gateway_queue_depth",
            "Requests waiting for an admission slot.",
            labels,
            registry=self.registry,
        )
        self.fallbacks = Counter(
            "llm_gateway_fallbacks",
            "Requests re-routed from one backend to another.",
            ["from_backend", "to_backend"],
            registry=self.registry,
        )
        self.output_tokens = Counter(
            "llm_gateway_output_tokens",
            "Completion tokens reported by upstream usage.",
            labels,
            registry=self.registry,
        )

    def init_backend(self, backend: str) -> None:
        """Create a backend's series up front, so its first error is visible to rate()."""
        self.requests.labels(backend, "ok")
        self.in_flight.labels(backend)
        self.ttft.labels(backend)
        self.tpot.labels(backend)
        self.prompt_tokens.labels(backend)
        self.output_tokens.labels(backend)

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
