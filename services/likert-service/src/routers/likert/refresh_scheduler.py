"""Which cached places are due for a refresh (pure core) — PRD "Background refresh &
cost guardrails"; service ADR-0001 (Tier-2).

Given the cache rows, ``now``, the TTL and a **monthly call-budget**, return the
``google_place_id``s **due** for a refresh: those whose rating is older than the TTL,
capped at the budget. This is the cost guardrail — the worker never spends more than the
budget in one pass, and never pays to refresh data still within its TTL.

No IO, no DB, no HTTP — the cache rows are read by ``ratings_repository`` and fed in, so
this decision is tested in isolation. The ``refresh_worker`` only loops over the list
this returns.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass(frozen=True)
class CachedPlace:
    """One matched place's cache state: its resolved ``google_place_id`` and when its
    rating was last fetched. ``fetched_at is None`` means it has been matched but never
    rated yet — the most-stale state, refreshed first."""

    google_place_id: str
    fetched_at: Optional[datetime]


def select_due(
    places: List[CachedPlace],
    *,
    now: datetime,
    ttl: timedelta,
    budget: int,
) -> List[str]:
    """Return the ``google_place_id``s due for a refresh, most-stale first, capped at
    ``budget``."""
    cutoff = now - ttl
    due = [p for p in places if p.fetched_at is None or p.fetched_at <= cutoff]
    # Most-stale first: never-fetched (None) before any timestamp, then oldest fetch
    # first — so a tight budget spends its calls where the cache is most out of date.
    due.sort(key=lambda p: (p.fetched_at is not None, p.fetched_at))
    return [p.google_place_id for p in due[:budget]]
