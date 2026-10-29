from __future__ import annotations

import pytest
from llm_bench.client import RequestResult
from llm_bench.metrics import percentile, summarize


@pytest.mark.parametrize(
    ("q", "expected"),
    [(0, 1.0), (50, 2.5), (100, 4.0), (25, 1.75)],
)
def test_percentile_interpolates_linearly(q: float, expected: float) -> None:
    assert percentile([4.0, 1.0, 3.0, 2.0], q) == pytest.approx(expected)


def test_percentile_edge_cases() -> None:
    assert percentile([], 50) is None
    assert percentile([7.0], 99) == 7.0
    with pytest.raises(ValueError, match="q must be"):
        percentile([1.0], 101)


def _ok(ttft: float, decode: float, tokens: int, prompt: int = 100) -> RequestResult:
    return RequestResult(
        ok=True,
        e2e_s=ttft + decode,
        ttft_s=ttft,
        decode_s=decode,
        output_tokens=tokens,
        prompt_tokens=prompt,
        token_source="usage",
        chunk_gaps_s=[decode / (tokens - 1)] * (tokens - 1),
    )


def test_summarize_computes_latency_and_throughput() -> None:
    results = [
        _ok(ttft=0.1, decode=1.0, tokens=11),  # 100 ms/token
        _ok(ttft=0.3, decode=2.0, tokens=11),  # 200 ms/token
        RequestResult(ok=False, e2e_s=0.01, error="boom"),
    ]
    summary = summarize(results, wall_s=2.0)

    assert summary.requests == 3
    assert summary.errors == 1
    assert summary.ttft_ms_p50 == pytest.approx(200)
    assert summary.tpot_ms_p50 == pytest.approx(150)
    assert summary.decode_tps_p50 == pytest.approx(7.5)
    assert summary.prefill_tps_p50 == pytest.approx((1000 + 100 / 0.3) / 2)
    assert summary.output_tokens_mean == pytest.approx(11)
    assert summary.output_tps == pytest.approx(22 / 2.0)
    assert summary.request_rate == pytest.approx(1.0)


def test_summarize_all_failed() -> None:
    summary = summarize([RequestResult(ok=False, e2e_s=0.1, error="x")], wall_s=0.1)

    assert summary.errors == 1
    assert summary.ttft_ms_p50 is None
    assert summary.output_tokens_mean is None
    assert summary.output_tps == 0
