"""Aggregate per-request results into the latency/throughput numbers that matter for serving."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from pydantic import BaseModel

from llm_bench.client import RequestResult


def percentile(values: Sequence[float], q: float) -> float | None:
    """Linear-interpolated percentile (same definition as numpy's default)."""
    if not values:
        return None
    if not 0 <= q <= 100:
        raise ValueError("q must be within [0, 100]")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q / 100
    lo, hi = math.floor(rank), math.ceil(rank)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def _scaled(value: float | None, factor: float) -> float | None:
    return None if value is None else value * factor


def _present(values: Iterable[float | None]) -> list[float]:
    return [v for v in values if v is not None]


class LevelSummary(BaseModel):
    """Metrics for one (engine, scenario, concurrency) cell.

    Latencies are per request; ``output_tps`` and ``request_rate`` are aggregate over the
    wall-clock time of the whole level, i.e. what the server sustains for all users at once.
    """

    requests: int
    errors: int
    wall_s: float
    ttft_ms_p50: float | None
    ttft_ms_p95: float | None
    tpot_ms_p50: float | None
    tpot_ms_p95: float | None
    itl_ms_p99: float | None
    decode_tps_p50: float | None
    prefill_tps_p50: float | None
    e2e_s_p50: float | None
    e2e_s_p95: float | None
    output_tokens_mean: float | None
    output_tps: float
    request_rate: float


def summarize(results: Sequence[RequestResult], wall_s: float) -> LevelSummary:
    ok = [r for r in results if r.ok]
    ttft = _present(r.ttft_s for r in ok)
    tpot = _present(r.tpot_s for r in ok)
    gaps = [gap for r in ok for gap in r.chunk_gaps_s]
    e2e = [r.e2e_s for r in ok]
    total_tokens = sum(r.output_tokens for r in ok)
    safe_wall = wall_s if wall_s > 0 else math.inf

    return LevelSummary(
        requests=len(results),
        errors=len(results) - len(ok),
        wall_s=wall_s,
        ttft_ms_p50=_scaled(percentile(ttft, 50), 1000),
        ttft_ms_p95=_scaled(percentile(ttft, 95), 1000),
        tpot_ms_p50=_scaled(percentile(tpot, 50), 1000),
        tpot_ms_p95=_scaled(percentile(tpot, 95), 1000),
        itl_ms_p99=_scaled(percentile(gaps, 99), 1000),
        decode_tps_p50=percentile(_present(r.decode_tps for r in ok), 50),
        prefill_tps_p50=percentile(_present(r.prefill_tps for r in ok), 50),
        e2e_s_p50=percentile(e2e, 50),
        e2e_s_p95=percentile(e2e, 95),
        output_tokens_mean=total_tokens / len(ok) if ok else None,
        output_tps=total_tokens / safe_wall,
        request_rate=len(ok) / safe_wall,
    )
