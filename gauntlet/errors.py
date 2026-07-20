"""Gauntlet error type.

Every malformed input (missing/empty/corrupt logs, bad packets) must raise
:class:`GauntletError` with a human-readable reason — the gauntlet never
emits a PASS it cannot stand behind (AGENTS.md §2: evidence integrity).
"""


class GauntletError(Exception):
    """Raised for any invalid gauntlet input; never produces a false PASS."""
