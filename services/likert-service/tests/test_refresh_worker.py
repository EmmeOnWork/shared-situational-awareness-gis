"""Acceptance test for the background refresh worker (task 06) — the double-loop
outer gate.

The worker's *decisions* live in the pure modules tested in isolation: which places
are due (``refresh_scheduler``) and which POI matches a Google place
(``place_matcher``). Here we assert the **orchestration's** observable effect over an
**injected fake Google client** (no live calls) and **patched repo seams** (the SQL is
manual-verify, like the sibling repos): a place past its TTL — or never fetched — gets
its rating fetched and **upserted into the cache**; a place still within its TTL is a
**no-op**; and the monthly budget caps how many places are refreshed in one pass.

Mirrors task 05's ``test_place_resolver``: the real ``refresh_scheduler`` runs
unmocked (that is the assembled decision under test), while the Google HTTP adapter and
the cache SQL are stood-in/patched.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.routers.likert.refresh_scheduler import CachedPlace
from src.routers.likert.refresh_worker import run_refresh

NOW = datetime(2026, 6, 29, tzinfo=timezone.utc)
TTL = timedelta(days=30)

# Three matched places in the cache: one never fetched (no rating yet), one stale
# (past the 30-day TTL), one fresh (within it). The fresh one must never be touched.
NEVER = CachedPlace(google_place_id="g-never", fetched_at=None)
STALE = CachedPlace(google_place_id="g-stale", fetched_at=NOW - timedelta(days=40))
FRESH = CachedPlace(google_place_id="g-fresh", fetched_at=NOW - timedelta(days=5))

RATINGS = {
    "g-never": (4.6, 120),
    "g-stale": (3.2, 40),
    "g-fresh": (5.0, 9),  # present, but should never be requested
}


class FakeGoogleClient:
    """Stands in for ``google_client``: returns a canned (rating, review-count) per
    place and records which places were actually fetched, so the worker runs without a
    live Google call (PRD: no live calls in tests)."""

    def __init__(self, ratings_by_place):
        self._ratings_by_place = ratings_by_place
        self.fetched = []

    def fetch_place_rating(self, google_place_id):
        self.fetched.append(google_place_id)
        return self._ratings_by_place[google_place_id]


def _patch_repos(cached_places):
    """Patch the worker's four manual-verify repo seams: no competitors to enumerate /
    resolve (the refresh phase is under test here), and the given cache rows. Returns
    the contextmanager stack's patches so the test can read the upsert spy."""
    return (
        patch(
            "src.routers.likert.refresh_worker.enumerate_all_competitor_pois",
            return_value=[],
        ),
        patch(
            "src.routers.likert.refresh_worker.list_resolved_poi_ids",
            return_value=set(),
        ),
        patch(
            "src.routers.likert.refresh_worker.list_cached_places",
            return_value=cached_places,
        ),
        patch("src.routers.likert.refresh_worker.upsert_place_rating"),
    )


def test_worker_refreshes_due_places_and_skips_within_ttl():
    client = FakeGoogleClient(RATINGS)
    enum_p, resolved_p, cached_p, upsert_p = _patch_repos([NEVER, STALE, FRESH])

    with enum_p, resolved_p, cached_p, upsert_p as upsert:
        summary = run_refresh(client=client, now=NOW, ttl=TTL, budget=100)

    # The two due places are fetched; the fresh one is left alone.
    assert set(client.fetched) == {"g-never", "g-stale"}
    assert "g-fresh" not in client.fetched

    # …and the fetched ratings are upserted into the cache (rating + review count).
    upserted = {c.args[0]: c.kwargs for c in upsert.call_args_list}
    assert upserted["g-never"]["rating"] == 4.6
    assert upserted["g-never"]["user_ratings_total"] == 120
    assert upserted["g-stale"]["rating"] == 3.2
    assert "g-fresh" not in upserted

    assert summary.refreshed == 2


def test_worker_stops_at_the_monthly_budget():
    """Two places are due but the budget allows only one Google call this period: the
    most-stale (the never-fetched one) is refreshed and the rest wait for next pass."""
    client = FakeGoogleClient(RATINGS)
    enum_p, resolved_p, cached_p, upsert_p = _patch_repos([NEVER, STALE, FRESH])

    with enum_p, resolved_p, cached_p, upsert_p as upsert:
        summary = run_refresh(client=client, now=NOW, ttl=TTL, budget=1)

    assert client.fetched == ["g-never"]
    assert [c.args[0] for c in upsert.call_args_list] == ["g-never"]
    assert summary.refreshed == 1
