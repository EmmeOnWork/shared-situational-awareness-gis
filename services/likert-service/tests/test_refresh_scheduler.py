"""Unit tests for the pure refresh scheduler (Tier-2 guardrail; PRD; task 06).

Pure-function-in-isolation style (cf. ``test_place_matcher``): no client, no DB — feed
the cache rows, ``now``, the TTL and the monthly call-budget, and assert which
``google_place_id``s come back **due** for a refresh. This is the cost guardrail: only
places past their TTL are refreshed, and never more than the budget allows in one pass.
"""

from datetime import datetime, timedelta, timezone

from src.routers.likert.refresh_scheduler import CachedPlace, select_due

NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)
TTL = timedelta(days=30)
BUDGET = 100


def test_selects_only_entries_past_ttl():
    """A place fetched 40 days ago is past the 30-day TTL (due); one fetched 5 days
    ago is still fresh and must be left alone."""
    stale = CachedPlace(google_place_id="g-stale", fetched_at=NOW - timedelta(days=40))
    fresh = CachedPlace(google_place_id="g-fresh", fetched_at=NOW - timedelta(days=5))

    due = select_due([fresh, stale], now=NOW, ttl=TTL, budget=BUDGET)

    assert due == ["g-stale"]


def test_a_never_fetched_place_is_due():
    """A matched place with no rating yet (``fetched_at is None``) is due — it has no
    cached Gradimento at all, so it is refreshed (and prioritised over merely-stale)."""
    never = CachedPlace(google_place_id="g-never", fetched_at=None)
    fresh = CachedPlace(google_place_id="g-fresh", fetched_at=NOW - timedelta(days=5))

    due = select_due([fresh, never], now=NOW, ttl=TTL, budget=BUDGET)

    assert due == ["g-never"]


def test_budget_caps_to_the_most_stale():
    """Three places are due but the budget allows only two calls this pass: the two
    most-stale are returned (never-fetched first, then oldest), so the cap is honoured
    and the staler data is refreshed first."""
    never = CachedPlace(google_place_id="g-never", fetched_at=None)
    older = CachedPlace(google_place_id="g-older", fetched_at=NOW - timedelta(days=90))
    old = CachedPlace(google_place_id="g-old", fetched_at=NOW - timedelta(days=40))

    due = select_due([old, never, older], now=NOW, ttl=TTL, budget=2)

    assert due == ["g-never", "g-older"]


def test_empty_input_is_empty():
    """No cache rows → nothing to refresh (the worker's first-ever pass before any
    identity is resolved)."""
    assert select_due([], now=NOW, ttl=TTL, budget=BUDGET) == []
