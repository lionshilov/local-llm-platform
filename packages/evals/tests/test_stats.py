from __future__ import annotations

import math

import pytest
from llm_evals.stats import Z_95, mcnemar_exact, mean, wilson_interval


@pytest.mark.parametrize(
    ("successes", "n", "low", "high"),
    [
        # Newcombe (1998), "Two-sided confidence intervals for the single proportion",
        # Statistics in Medicine 17:857-872, Table I, method 3 (score, no continuity
        # correction). Published to four decimals.
        (81, 263, 0.2553, 0.3662),
        (15, 148, 0.0624, 0.1605),
        (0, 20, 0.0000, 0.1611),
        (1, 29, 0.0061, 0.1718),
    ],
)
def test_wilson_matches_published_values(successes: int, n: int, low: float, high: float) -> None:
    assert wilson_interval(successes, n) == pytest.approx((low, high), abs=5e-5)


@pytest.mark.parametrize(("successes", "n"), [(1, 7), (13, 30), (29, 30), (100, 400)])
def test_wilson_bounds_solve_the_score_equation(successes: int, n: int) -> None:
    """By definition, each bound p satisfies |p_hat - p| = z * sqrt(p (1 - p) / n)."""
    p_hat = successes / n
    for p in wilson_interval(successes, n):
        assert abs(p_hat - p) == pytest.approx(Z_95 * math.sqrt(p * (1 - p) / n), rel=1e-9)


def test_wilson_is_narrower_with_more_data_and_contains_the_estimate() -> None:
    small = wilson_interval(8, 10)
    large = wilson_interval(80, 100)
    assert small[0] < 0.8 < small[1]
    assert large[1] - large[0] < small[1] - small[0]


def test_wilson_edge_cases() -> None:
    assert wilson_interval(0, 0) == (0.0, 1.0)
    with pytest.raises(ValueError, match="successes"):
        wilson_interval(3, 2)


@pytest.mark.parametrize(
    ("only_a", "only_b", "p"),
    [
        (0, 0, 1.0),
        (3, 3, 1.0),
        (0, 5, 2 / 32),
        (1, 9, 2 * (1 + 10) / 1024),
        (6, 1, 2 * (1 + 7) / 128),
        (2, 12, 2 * (1 + 14 + 91) / 2**14),
    ],
)
def test_mcnemar_exact(only_a: int, only_b: int, p: float) -> None:
    assert mcnemar_exact(only_a, only_b) == pytest.approx(p)
    assert mcnemar_exact(only_b, only_a) == pytest.approx(p)


def test_mcnemar_rejects_negative_counts() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        mcnemar_exact(-1, 2)


def test_mean_skips_missing_values() -> None:
    assert mean([1.0, None, 3.0]) == 2.0
    assert mean([None]) is None
