"""Paired analysis must not manufacture confidence or lose inconvenient runs.

The failure modes these tests close are the ones that make a small campaign
read like a large one: silently dropping the runs that never settled, producing
an interval from a single observation, or letting the bootstrap wander between
reruns so the "interval" is really a knob.
"""

import math

import pytest

from campaign.errors import CampaignError
from campaign.paired import bootstrap_ci, describe, pair_metric

SEEDS = list(range(20))
BSEED = 20260814


def const(value, seeds=SEEDS):
    return {s: value for s in seeds}


class TestBootstrapIsDeterministic:
    def test_same_input_same_interval(self):
        v = [0.1 * i for i in range(20)]
        assert bootstrap_ci(v, BSEED) == bootstrap_ci(v, BSEED)

    def test_different_seed_gives_a_different_interval(self):
        v = [0.1 * i for i in range(20)]
        assert bootstrap_ci(v, BSEED) != bootstrap_ci(v, BSEED + 1)

    def test_interval_brackets_the_mean(self):
        v = [1.0, 1.1, 0.9, 1.2, 0.8, 1.05, 0.95, 1.3, 0.7, 1.0]
        lo, hi = bootstrap_ci(v, BSEED)
        assert lo < sum(v) / len(v) < hi

    def test_refuses_to_invent_precision_from_one_point(self):
        assert bootstrap_ci([1.0], BSEED) == (None, None)
        assert bootstrap_ci([], BSEED) == (None, None)

    def test_rejects_non_finite_input(self):
        with pytest.raises(CampaignError, match="requires finite values"):
            bootstrap_ci([1.0, math.inf], BSEED)


class TestPairing:
    def test_a_clear_improvement_is_reported_as_one(self):
        m = pair_metric("tracking_rms_error", True, const(0.1), const(0.4),
                        SEEDS, BSEED)
        assert m.n_finite_pairs == 20
        assert m.mean_difference == pytest.approx(-0.3)
        assert m.n_filtered_better == 20
        assert m.filtered_better_fraction == 1.0

    def test_a_regression_is_reported_as_one(self):
        # The harness must never cook the sign.
        m = pair_metric("tracking_rms_error", True, const(0.4), const(0.1),
                        SEEDS, BSEED)
        assert m.mean_difference == pytest.approx(0.3)
        assert m.n_filtered_better == 0
        assert "WORSE" in describe(m)

    def test_higher_is_better_metric_flips_the_verdict(self):
        m = pair_metric("filter_attenuation_db", False, const(40.0), const(0.0),
                        SEEDS, BSEED)
        assert m.n_filtered_better == 20
        assert "better" in describe(m)


class TestNonFiniteRunsAreResultsNotMissingData:
    def test_infinite_settling_is_kept_in_the_counts(self):
        # An unfiltered run that never settles is THE result. Dropping it would
        # flatter the unfiltered arm by silently deleting its worst runs.
        m = pair_metric("settling_time_s", True, const(5.0), const(math.inf),
                        SEEDS, BSEED)
        assert m.n_pairs == 20
        assert m.n_nonfinite_pairs == 20
        assert m.n_finite_pairs == 0
        assert m.mean_difference is None
        assert m.ci_low is None
        # Direction is still known: finite beats infinite on a lower-is-better
        # metric, so the win fraction is 100% even with no interval.
        assert m.n_filtered_better == 20
        assert m.filtered_better_fraction == 1.0
        assert "non-finite" in m.note

    def test_mixed_finite_and_infinite(self):
        f = const(5.0)
        u = {s: (math.inf if s < 10 else 8.0) for s in SEEDS}
        m = pair_metric("settling_time_s", True, f, u, SEEDS, BSEED)
        assert m.n_finite_pairs == 10
        assert m.n_nonfinite_pairs == 10
        assert m.n_filtered_better == 20
        assert m.ci_low is not None

    def test_infinite_on_the_filtered_side_counts_against_filtered(self):
        m = pair_metric("settling_time_s", True, const(math.inf), const(5.0),
                        SEEDS, BSEED)
        assert m.n_filtered_better == 0

    def test_describe_refuses_when_there_is_nothing_finite(self):
        m = pair_metric("settling_time_s", True, const(5.0), const(math.inf),
                        SEEDS, BSEED)
        assert "no finite paired differences" in describe(m)


class TestIncompletePairs:
    def test_a_missing_arm_is_counted_not_ignored(self):
        f = {s: 0.1 for s in SEEDS if s != 7}
        m = pair_metric("tracking_rms_error", True, f, const(0.4), SEEDS, BSEED)
        assert m.n_pairs == 20
        assert m.n_incomplete_pairs == 1
        assert m.n_finite_pairs == 19
        assert "incomplete" in m.note

    def test_every_seed_appears_in_the_pair_list_regardless(self):
        f = {s: 0.1 for s in SEEDS if s != 7}
        m = pair_metric("tracking_rms_error", True, f, const(0.4), SEEDS, BSEED)
        assert [p[0] for p in m.pairs] == SEEDS
        assert m.pairs[7][1] is None

    def test_serialization_keeps_every_seed_and_encodes_inf(self):
        m = pair_metric("settling_time_s", True, const(5.0), const(math.inf),
                        SEEDS, BSEED)
        d = m.to_dict()
        assert len(d["pairs"]) == 20
        assert d["pairs"][0]["unfiltered"] == "inf"
