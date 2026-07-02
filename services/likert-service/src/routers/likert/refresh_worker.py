"""Background refresh worker — fills the ratings cache for all comuni (task 06).

Closes the loop so the widget shows **real** Gradimento everywhere with no seeding.
One pass:

1. **Enumerate** every Competitor POI across all comuni in the DB.
2. **Resolve** the identity of the ones never seen before — match each to a Google
   place (or record ``no_match``) so a place is matched only once.
3. **Schedule** which matched places are due for a rating refresh (past TTL, or never
   rated), capped at the **monthly call-budget**.
4. **Refresh** each due place's rating + review count via the Google client and
   **upsert** it into the cache, restarting its TTL clock.

The worker is pure orchestration: every *decision* lives in a module tested in
isolation — the match in ``place_matcher``, the due-set + budget in
``refresh_scheduler``. So the worker itself is manual-verify (PRD), exercised by the
acceptance test over a fake Google client + patched repo seams. Re-running within the
TTL makes no Google calls (a no-op); after the TTL, due places refresh.

Run it as a cron/loop entrypoint: ``python -m src.routers.likert.refresh_worker``
(``make refresh``). The TTL and budget are config (``TTL_DAYS``, ``MONTHLY_BUDGET``).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.config import get_settings

from .competitor_repository import enumerate_all_competitor_pois
from .google_client import GoogleClient
from .place_repository import list_resolved_poi_ids
from .place_resolver import resolve_identities
from .ratings_repository import list_cached_places, upsert_place_rating
from .refresh_scheduler import select_due


@dataclass(frozen=True)
class RefreshSummary:
    """An inspectable tally of one worker pass: how many new identities were resolved
    and how many ratings were refreshed (≤ the budget)."""

    resolved: int
    refreshed: int


def run_refresh(
    *,
    client=None,
    now: Optional[datetime] = None,
    ttl: Optional[timedelta] = None,
    budget: Optional[int] = None,
) -> RefreshSummary:
    """Run one refresh pass and return its summary.

    Args:
        client: the Google client (``find_candidates`` + ``fetch_place_rating``);
            injected so tests pass a fake and no live call is made. Defaults to a real
            ``GoogleClient``.
        now / ttl / budget: the freshness clock, cache TTL and monthly call-budget;
            default to ``now(UTC)`` and the service settings.
    """
    settings = get_settings()
    if client is None:
        client = GoogleClient()
    if now is None:
        now = datetime.now(timezone.utc)
    if ttl is None:
        ttl = timedelta(days=settings.ttl_days)
    if budget is None:
        budget = settings.monthly_budget

    # 1–2. Resolve the identity of competitors we have never seen (matching is the
    # one-time cost; the already-resolved — match or no_match — are skipped).
    pois = enumerate_all_competitor_pois()
    already_resolved = list_resolved_poi_ids()
    unresolved = [poi for poi in pois if poi.poi_id not in already_resolved]
    summary = resolve_identities(unresolved, client=client)

    # 3–4. Refresh the due ratings, up to the budget; a place left out this pass is
    # picked up next period (the budget is honoured mid-pass).
    due = select_due(list_cached_places(), now=now, ttl=ttl, budget=budget)
    for google_place_id in due:
        rating, user_ratings_total = client.fetch_place_rating(google_place_id)
        upsert_place_rating(
            google_place_id,
            rating=rating,
            user_ratings_total=user_ratings_total,
        )

    return RefreshSummary(resolved=summary.matched, refreshed=len(due))


def main() -> None:
    """Cron/loop entrypoint: run one pass and print its summary. Scheduled externally
    (cron) per TTL period; resumes next period if the budget stops it mid-pass."""
    summary = run_refresh()
    print(
        f"likert refresh: resolved {summary.resolved} new identities, "
        f"refreshed {summary.refreshed} ratings"
    )


if __name__ == "__main__":
    main()
