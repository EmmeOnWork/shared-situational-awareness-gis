"""Cached online ratings for competitor POIs, from the shared DB (read side).

Given the competitor POI ids the ``competitor_repository`` resolved, return each
one's cached Google rating by joining the two owned tables: the permanent identity
map ``likert_poi_place`` (poi_id → google_place_id) and the TTL'd cache
``likert_place_rating`` (rating, user_ratings_total, fetched_at). Only POIs with a
confident match **and** a cached rating come back — an unmatched (`no_match`) or
uncached competitor is simply omitted, so a wrong/absent match can never attach a
0★ that would distort the pooled Gradimento.

The data route reads **only** this cache — never a live Google call on a widget
request (PRD; ADR-0001). The cache is filled by the background refresh worker
(``refresh_worker.py``); here we read whatever it has seeded.

A deep module: the router sees ``fetch_ratings(poi_ids) -> {poi_id: PlaceRating}``;
the join and the shared-DB session live entirely behind it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from src.config.pgsql_config import get_session_context, text

from .refresh_scheduler import CachedPlace


@dataclass(frozen=True)
class PlaceRating:
    """One competitor's cached rating: the monolith POI id, its 1–5 average, its
    review count, and when the cache last fetched it (drives "aggiornato il …")."""

    poi_id: int
    rating: float
    n_ratings: int
    fetched_at: datetime


# Identity map → cache join, scoped to the given competitor POIs. Bound params only
# (``:poi_ids`` is an int array, matched with ``= ANY``). Excludes the unmatchable
# (`no_match`) and the as-yet-unresolved (NULL place id); the inner join to the
# cache drops POIs whose rating hasn't been fetched. ``user_ratings_total`` is
# aliased to the ``n_ratings`` the Gradimento weights.
RATINGS_FOR_POIS_QUERY = text(
    """
    SELECT pp.poi_id            AS poi_id,
           pr.rating            AS rating,
           pr.user_ratings_total AS n_ratings,
           pr.fetched_at        AS fetched_at
    FROM likert_poi_place pp
    JOIN likert_place_rating pr ON pr.google_place_id = pp.google_place_id
    WHERE pp.poi_id = ANY(:poi_ids)
      AND pp.no_match = false
      AND pp.google_place_id IS NOT NULL
    """
)


def fetch_ratings(poi_ids: List[int]) -> Dict[int, PlaceRating]:
    """Return ``{poi_id: PlaceRating}`` for the matched + rated subset of ``poi_ids``.

    An empty ``poi_ids`` short-circuits without touching the DB. POIs with no
    confident match or no cached rating are absent from the result (never a
    fabricated 0★) — the caller treats an empty map as "nothing to rate".
    """
    if not poi_ids:
        return {}

    with get_session_context() as session:
        rows = (
            session.execute(RATINGS_FOR_POIS_QUERY, {"poi_ids": list(poi_ids)})
            .mappings()
            .all()
        )

    return {
        row["poi_id"]: PlaceRating(
            poi_id=row["poi_id"],
            rating=row["rating"],
            n_ratings=row["n_ratings"],
            fetched_at=row["fetched_at"],
        )
        for row in rows
    }


# The refresh worker's view of the cache: every confidently-matched place and when —
# if ever — its rating was last fetched. A LEFT JOIN so a place matched but not yet
# rated comes back with ``fetched_at = NULL`` (the scheduler treats it as most-stale).
# The unmatchable (`no_match`) are excluded — there is nothing to refresh for them.
CACHED_PLACES_QUERY = text(
    """
    SELECT pp.google_place_id AS google_place_id,
           pr.fetched_at      AS fetched_at
    FROM likert_poi_place pp
    LEFT JOIN likert_place_rating pr ON pr.google_place_id = pp.google_place_id
    WHERE pp.no_match = false
      AND pp.google_place_id IS NOT NULL
    """
)


def list_cached_places() -> List[CachedPlace]:
    """Return every matched place's cache state (``google_place_id`` + ``fetched_at``,
    ``None`` when never rated) — the rows the ``refresh_scheduler`` ranks for refresh."""
    with get_session_context() as session:
        rows = session.execute(CACHED_PLACES_QUERY).mappings().all()

    return [
        CachedPlace(
            google_place_id=row["google_place_id"],
            fetched_at=row["fetched_at"],
        )
        for row in rows
    ]


# Upsert one cache row: the place's fresh 1–5 average + review count, ``fetched_at``
# bumped to now() so the TTL clock restarts. Bound params only; a row already present
# is overwritten in place (``ON CONFLICT … DO UPDATE``), never duplicated — the cache
# is rebuilt by upsert, never purged.
UPSERT_PLACE_RATING_QUERY = text(
    """
    INSERT INTO likert_place_rating
        (google_place_id, rating, user_ratings_total, fetched_at)
    VALUES
        (:google_place_id, :rating, :user_ratings_total, now())
    ON CONFLICT (google_place_id) DO UPDATE SET
        rating             = EXCLUDED.rating,
        user_ratings_total = EXCLUDED.user_ratings_total,
        fetched_at         = EXCLUDED.fetched_at
    """
)


def upsert_place_rating(
    google_place_id: str,
    *,
    rating: float,
    user_ratings_total: int,
) -> None:
    """Persist a freshly-fetched Google rating into the TTL'd cache (resetting its
    ``fetched_at`` to now). Commits the row."""
    with get_session_context() as session:
        session.execute(
            UPSERT_PLACE_RATING_QUERY,
            {
                "google_place_id": google_place_id,
                "rating": rating,
                "user_ratings_total": user_ratings_total,
            },
        )
        session.commit()
