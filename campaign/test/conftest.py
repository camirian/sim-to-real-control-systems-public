"""Shared fixtures: directories of synthetic gauntlet evidence packets.

Every packet is produced by :mod:`campaign.synth`, which builds real
``CheckResult`` objects and runs them through :func:`gauntlet.evidence.build_packet`
+ :func:`write_packet` — no hand-rolled JSON. See :mod:`campaign.synth` for why
these are synthetic and how per-seed jitter is applied.
"""

import pytest

from campaign.synth import write_campaign


@pytest.fixture()
def campaign_dir(tmp_path):
    """A balanced 4-filtered / 4-unfiltered campaign (filtered wins cleanly)."""
    d = tmp_path / "evidence"
    write_campaign(d, n_filtered=4, n_unfiltered=4)
    return d
