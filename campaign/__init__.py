"""campaign — results aggregation for the seeded filtered-vs-unfiltered sweep.

REQ-S2R-102: consume a directory of gauntlet evidence packets
(``run-<id>.json``, the format :mod:`gauntlet.evidence` emits) and produce the
MASTER_PLAN "money table" — per-condition pass rate, mean/median tracking RMS,
settling, overshoot, filter attenuation, and the headline filtered-vs-unfiltered
deltas — as both ``results_table.md`` (commit-quality markdown) and
``results.json`` (deterministic, machine-readable).

Pure Python, deterministic (sorted keys, fixed float formatting, wall-clock
time only via an explicit argument), no ROS/Isaac. The aggregator reuses
:func:`gauntlet.evidence.load_packet` so every packet is validated the same way
the gauntlet validates it — a corrupt packet can never sneak into the table.

Public API:

- :func:`campaign.aggregate.aggregate_directory` — evidence dir -> CampaignResult
- :func:`campaign.render.render_results_table` / :func:`render_results_json`
- :class:`campaign.errors.CampaignError`
"""

from __future__ import annotations

__version__ = "0.1.0"

SCHEMA_VERSION = 1

#: The two campaign conditions compared in the money table. A run's condition
#: is the leading token of its run id (``filtered-0001`` -> ``filtered``); the
#: campaign runner writes ids following this convention (see run_campaign.py).
FILTERED = "filtered"
UNFILTERED = "unfiltered"
CONDITIONS = (FILTERED, UNFILTERED)

__all__ = ["__version__", "SCHEMA_VERSION", "FILTERED", "UNFILTERED", "CONDITIONS"]
