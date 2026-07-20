"""campaign error type.

Mirrors :class:`gauntlet.errors.GauntletError`: any input the aggregator cannot
honestly turn into a results table (empty/absent evidence directory, no
recognizable runs after skipping malformed packets) raises
:class:`CampaignError`. Individual malformed packets are skipped with a recorded
warning, never silently dropped and never allowed to corrupt the table
(see :mod:`campaign.aggregate`).
"""


class CampaignError(Exception):
    """Raised when a campaign directory cannot be aggregated into a table."""
