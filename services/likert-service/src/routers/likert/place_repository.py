"""Write side of the permanent identity map ``likert_poi_place`` (task 05).

The read side (``ratings_repository``) joins this map to the cache for the data
route; here the resolve step **upserts** it: one row per competitor POI, carrying its
resolved ``google_place_id`` (+confidence) on a confident match, or ``no_match=true``
when nothing matched — so the worker doesn't burn calls re-resolving the unmatchable
every cycle. Identity is stored **permanently** (ToS-allowed); a re-resolve overwrites
the row in place (``ON CONFLICT … DO UPDATE``), never duplicates it.

A deep module: the resolver sees one call, ``upsert_poi_place(...)``; the SQL and the
shared-DB session live behind it. The DDL is owned by ``db/likert-schema.sql`` (the
service only ever issues DML). Like the sibling repos' SQL, the statement is
exercised end-to-end against the shared DB (manual-verify), not in unit tests.
"""

from typing import Optional, Set

from src.config.pgsql_config import get_session_context, text

# Upsert one identity-map row. Bound params only. A row already present (re-resolve)
# is overwritten in place — including ``matched_at`` bumped to now() — so the map is
# rebuilt by upsert, never duplicated. ``google_place_id`` is NULL on a no_match.
UPSERT_POI_PLACE_QUERY = text(
    """
    INSERT INTO likert_poi_place
        (poi_id, google_place_id, match_confidence, no_match, matched_at)
    VALUES
        (:poi_id, :google_place_id, :match_confidence, :no_match, now())
    ON CONFLICT (poi_id) DO UPDATE SET
        google_place_id  = EXCLUDED.google_place_id,
        match_confidence = EXCLUDED.match_confidence,
        no_match         = EXCLUDED.no_match,
        matched_at       = EXCLUDED.matched_at
    """
)


def upsert_poi_place(
    poi_id: int,
    *,
    google_place_id: Optional[str],
    match_confidence: Optional[float],
    no_match: bool,
) -> None:
    """Persist a POI's resolved identity: a confident match (``google_place_id`` +
    ``match_confidence``, ``no_match=False``) or a recorded non-match
    (``google_place_id=None``, ``no_match=True``). Commits the row."""
    with get_session_context() as session:
        session.execute(
            UPSERT_POI_PLACE_QUERY,
            {
                "poi_id": poi_id,
                "google_place_id": google_place_id,
                "match_confidence": match_confidence,
                "no_match": no_match,
            },
        )
        session.commit()


# Every POI already in the identity map — matched or recorded ``no_match`` alike. The
# worker subtracts these from the enumerated competitors so it resolves each place's
# identity only once (matching is the one-time cost; a `no_match` is not re-tried).
RESOLVED_POI_IDS_QUERY = text("SELECT poi_id FROM likert_poi_place")


def list_resolved_poi_ids() -> Set[int]:
    """Return the set of POI ids already resolved (matched or ``no_match``), so the
    worker only resolves the ones it has never seen."""
    with get_session_context() as session:
        rows = session.execute(RESOLVED_POI_IDS_QUERY).scalars().all()
    return set(rows)
