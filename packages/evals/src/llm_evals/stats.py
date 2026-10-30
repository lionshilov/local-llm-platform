"""Small-sample statistics for pass rates.

With 30 items, one item is 3.3 percentage points, and the 95% interval for 24/30 (80%) runs
from 63% to 90%. The Wilson score interval stays inside [0, 1] and keeps close to its
nominal coverage at small n and extreme rates, where the textbook normal ("Wald") interval
collapses to zero width at 0% or 100%.

Two backends answering the *same* items are compared with McNemar's exact test, which
looks only at the items where they disagree. That is far more sensitive than checking
whether two independent intervals overlap.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

Z_95 = 1.959963984540054  # two-sided 95% quantile of the standard normal


def wilson_interval(successes: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if not 0 <= successes <= n:
        raise ValueError(f"need 0 <= successes <= n, got {successes}/{n}")
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    # Clamp float noise; the exact bounds at 0 and n are 0 and 1.
    low = 0.0 if successes == 0 else max(0.0, center - half_width)
    high = 1.0 if successes == n else min(1.0, center + half_width)
    return low, high


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value from the discordant pair counts.

    ``only_a``: items only A got right; ``only_b``: items only B got right. Under the null
    hypothesis each disagreement is a fair coin flip, so this is a binomial test.
    """
    if only_a < 0 or only_b < 0:
        raise ValueError("counts must be non-negative")
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(only_a, only_b) + 1)) / (1 << n)
    return min(1.0, 2 * tail)


def mean(values: Iterable[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None
