"""Paired filtered-vs-unfiltered analysis with honest uncertainty (REQ-S2R-102).

The campaign runs each seed under BOTH conditions, so the two arms see the
identical disturbance realization. That pairing is the whole reason a 20-run
comparison is worth anything: the per-seed difference cancels the variation
between seeds, which is far larger than the effect being measured.

What this module deliberately does NOT do:

- **No p-values, no significance claims.** With n=20 paired observations from
  one scenario on one machine, a significance test would dress a small,
  non-random sample as an inference about a population that was never sampled.
  Confidence intervals and the raw per-seed distribution are reported instead.
- **No dropping of non-finite values.** An unfiltered run that never settles has
  ``settling_time_s = inf``. That is the RESULT, not missing data. Non-finite
  pairs are counted and reported explicitly; they are excluded only from the
  interval arithmetic (which is undefined on inf), never from the denominator.
- **No re-seeding to taste.** The bootstrap RNG is seeded from the frozen
  manifest, so the interval is a deterministic function of the data.

Pure Python + NumPy; no ROS, no Isaac. Runs offline against committed evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from campaign.errors import CampaignError


@dataclass(frozen=True)
class PairedMetric:
    """One metric's paired comparison across every seed in the campaign."""

    name: str
    lower_is_better: bool
    #: (seed, filtered_value, unfiltered_value) for every seed, in seed order.
    pairs: List[Tuple[int, Optional[float], Optional[float]]]
    #: filtered - unfiltered, finite pairs only, in seed order.
    finite_differences: List[float]
    n_pairs: int
    n_finite_pairs: int
    n_nonfinite_pairs: int
    n_incomplete_pairs: int
    mean_difference: Optional[float]
    median_difference: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    ci_level: float
    #: Fraction of finite pairs in which filtered was better. Distribution-free
    #: and robust to the outliers a small campaign is full of.
    filtered_better_fraction: Optional[float]
    n_filtered_better: int
    note: str = ""

    def to_dict(self) -> dict:
        def j(v):
            if v is None:
                return None
            if math.isinf(v):
                return "inf" if v > 0 else "-inf"
            if math.isnan(v):
                return "nan"
            return v

        return {
            "name": self.name,
            "lower_is_better": self.lower_is_better,
            "n_pairs": self.n_pairs,
            "n_finite_pairs": self.n_finite_pairs,
            "n_nonfinite_pairs": self.n_nonfinite_pairs,
            "n_incomplete_pairs": self.n_incomplete_pairs,
            "mean_difference": j(self.mean_difference),
            "median_difference": j(self.median_difference),
            "ci_low": j(self.ci_low),
            "ci_high": j(self.ci_high),
            "ci_level": self.ci_level,
            "filtered_better_fraction": j(self.filtered_better_fraction),
            "n_filtered_better": self.n_filtered_better,
            "pairs": [
                {"seed": s, "filtered": j(f), "unfiltered": u_
                 if not isinstance(u_, float) else j(u_)}
                for s, f, u_ in self.pairs
            ],
            "note": self.note,
        }


def bootstrap_ci(
    values: Sequence[float],
    seed: int,
    resamples: int = 10000,
    level: float = 0.95,
) -> Tuple[Optional[float], Optional[float]]:
    """Deterministic percentile bootstrap CI for the mean of ``values``.

    Seeded from the frozen manifest, so the same evidence always yields the
    same interval — an interval that moved between reruns would be a knob.
    Returns ``(None, None)`` for fewer than two values: an interval from one
    observation would be a fabricated precision.
    """
    v = np.asarray([float(x) for x in values], dtype=float)
    if v.size < 2:
        return None, None
    if not np.all(np.isfinite(v)):
        raise CampaignError("bootstrap_ci requires finite values")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(int(resamples), v.size))
    means = v[idx].mean(axis=1)
    alpha = (1.0 - level) / 2.0
    lo, hi = np.quantile(means, [alpha, 1.0 - alpha])
    return float(lo), float(hi)


def pair_metric(
    name: str,
    lower_is_better: bool,
    filtered: Dict[int, Optional[float]],
    unfiltered: Dict[int, Optional[float]],
    seeds: Sequence[int],
    bootstrap_seed: int,
    resamples: int = 10000,
    level: float = 0.95,
) -> PairedMetric:
    """Build the paired comparison for one metric over the campaign's seeds."""
    pairs: List[Tuple[int, Optional[float], Optional[float]]] = []
    diffs: List[float] = []
    n_nonfinite = 0
    n_incomplete = 0
    n_better = 0

    for seed in seeds:
        f = filtered.get(seed)
        u = unfiltered.get(seed)
        pairs.append((int(seed), f, u))
        if f is None or u is None:
            # One arm of this seed is missing (invalid/failed run). The pair
            # cannot be differenced, but it is still counted and reported.
            n_incomplete += 1
            continue
        if not (math.isfinite(f) and math.isfinite(u)):
            n_nonfinite += 1
            # A directional verdict is still available when exactly one side is
            # infinite, so the pair contributes to the win fraction even though
            # it cannot contribute to the interval.
            if math.isfinite(f) and math.isinf(u):
                n_better += 1 if lower_is_better else 0
            elif math.isinf(f) and math.isfinite(u):
                n_better += 0 if lower_is_better else 1
            continue
        d = f - u
        diffs.append(d)
        if (d < 0) if lower_is_better else (d > 0):
            n_better += 1

    n_comparable = len(diffs) + n_nonfinite
    ci_low, ci_high = (None, None)
    note = ""
    if diffs:
        ci_low, ci_high = bootstrap_ci(diffs, bootstrap_seed, resamples, level)
    if n_nonfinite:
        note = (
            f"{n_nonfinite}/{len(seeds)} pairs contain a non-finite value "
            f"(e.g. a run that never settles); those pairs are excluded from "
            f"the interval but retained in the counts and the win fraction"
        )
    if n_incomplete:
        note = (note + "; " if note else "") + (
            f"{n_incomplete}/{len(seeds)} pairs are incomplete (a run was "
            f"invalid or failed) and cannot be differenced"
        )

    return PairedMetric(
        name=name,
        lower_is_better=lower_is_better,
        pairs=pairs,
        finite_differences=diffs,
        n_pairs=len(seeds),
        n_finite_pairs=len(diffs),
        n_nonfinite_pairs=n_nonfinite,
        n_incomplete_pairs=n_incomplete,
        mean_difference=(sum(diffs) / len(diffs)) if diffs else None,
        median_difference=float(np.median(diffs)) if diffs else None,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_level=level,
        filtered_better_fraction=(n_better / n_comparable) if n_comparable else None,
        n_filtered_better=n_better,
        note=note,
    )


def describe(metric: PairedMetric, unit: str = "") -> str:
    """One honest sentence about a paired metric, or an explicit refusal."""
    u = f" {unit}" if unit else ""
    if metric.mean_difference is None:
        return (
            f"{metric.name}: no finite paired differences "
            f"({metric.n_nonfinite_pairs} non-finite, "
            f"{metric.n_incomplete_pairs} incomplete of {metric.n_pairs})."
        )
    direction = "lower" if metric.lower_is_better else "higher"
    better = "better" if (
        (metric.mean_difference < 0) == metric.lower_is_better
    ) else "WORSE"
    ci = (
        f"95% CI [{metric.ci_low:.4g}, {metric.ci_high:.4g}]{u}"
        if metric.ci_low is not None else "no interval (n<2)"
    )
    return (
        f"{metric.name}: filtered minus unfiltered = "
        f"{metric.mean_difference:+.4g}{u} ({better}; {direction} is better), "
        f"{ci}, over {metric.n_finite_pairs}/{metric.n_pairs} finite pairs; "
        f"filtered better in {metric.n_filtered_better}/{metric.n_pairs}."
    )
