"""The comune-scoped Competitor set for a Vocazione, from the shared DB.

Given a comune (a monolith **region**) and a Vocazione's FSQ category-label
prefixes, return the Competitor POIs in that comune — the **same** set the
Concorrenza map layer paints. This is the monolith's ``GET /pois/competitors``
join (``regions → region_areas → areas[type 3] → poi_area_lookup → pois``,
``source='foursquare_os'``, prefix match on ``fsq_category_labels``) **copied, not
imported** (ADR-0001 shared DB, referenced by id/name only), but returning rows the
Gradimento can average rather than a GeoJSON FeatureCollection the map can paint.

A deep module: the router sees ``find_competitors(region_id, prefixes) ->
list[Competitor]``; the spatial join, the JSON taxonomy unwrapping and the shared-DB
session live entirely behind it. ``categoria`` is the leaf of each FSQ label (e.g.
"Spa"), derived the same way the monolith's popup derives it.
"""

from dataclasses import dataclass
from typing import List

from src.config.pgsql_config import get_session_context, text

from .place_resolver import ResolvablePoi
from .vocazione_competitors import VOCAZIONE_COMPETITORS


@dataclass(frozen=True)
class Competitor:
    """One Competitor POI in the comune: the monolith POI id (referenced by id
    only), its name, and a human-readable categoria (the leaf of its FSQ labels).
    Ratings are attached in a later slice — this record carries identity only."""

    poi_id: int
    name: str
    categoria: str


# Comune-scoped competitor join: the foursquare_os POIs in the region whose
# ``fsq_category_labels`` start with one of the Vocazione's prefixes. Bound params
# only (``:like_patterns`` is ``prefix || '%'`` built by the caller). ``categoria``
# is the distinct leaf(s) of those labels — the same derivation the Concorrenza
# popup uses. Copy of the monolith's ``/pois/competitors`` query, kept read-only.
COMPETITORS_IN_COMUNE_QUERY = text(
    """
    SELECT p.id AS poi_id,
           p.name AS name,
           (
               SELECT string_agg(DISTINCT split_part(lbl, ' > ', -1), ', ')
               FROM jsonb_array_elements_text(
                   (p.metadata->>'fsq_category_labels')::jsonb
               ) AS lbl
           ) AS categoria
    FROM regions r
    JOIN region_areas ra ON ra.region_id = r.id
    JOIN areas a ON ra.area_id = a.id AND a.area_type_id = 3
    JOIN poi_area_lookup pal ON pal.area_id = a.id
    JOIN pois p ON pal.poi_id = p.id
    WHERE r.id = :region_id
      AND p.source = 'foursquare_os'
      AND jsonb_exists(p.metadata, 'fsq_category_labels')
      AND EXISTS (
          SELECT 1
          FROM jsonb_array_elements_text(
              (p.metadata->>'fsq_category_labels')::jsonb
          ) AS lbl
          WHERE lbl LIKE ANY(:like_patterns)
      )
    ORDER BY p.name
    """
)


def find_competitors(region_id: int, prefixes: List[str]) -> List[Competitor]:
    """Return the comune's Competitor POIs whose FSQ labels match any ``prefix``.

    Args:
        region_id: the resolved comune (monolith region id).
        prefixes: the Vocazione's FSQ category-label prefixes (non-empty — the
            caller short-circuits an empty map to ``no_competitors`` and never
            calls here).

    Returns:
        The matching Competitors (identity + categoria), ordered by name; an empty
        list when the comune has no competitor of this kind.
    """
    like_patterns = [prefix + "%" for prefix in prefixes]
    with get_session_context() as session:
        rows = (
            session.execute(
                COMPETITORS_IN_COMUNE_QUERY,
                {"region_id": region_id, "like_patterns": like_patterns},
            )
            .mappings()
            .all()
        )

    return [
        Competitor(
            poi_id=row["poi_id"],
            name=row["name"],
            categoria=row["categoria"],
        )
        for row in rows
    ]


# Every Competitor POI across ALL comuni — the worker's resolve universe. A
# ``foursquare_os`` POI (with coordinates) whose ``fsq_category_labels`` start with any
# Vocazione's prefix; the union over all 16 Vocazioni's prefixes is built by the
# caller and passed as ``:like_patterns``. No comune join: every such POI sits in some
# comune, so the union over all comuni is exactly "matches some Vocazione anywhere".
# ``ST_Y/ST_X`` of the point geometry give the lat/lng the matcher needs. DISTINCT so a
# POI matching several prefixes is enumerated once. Manual-verify SQL like the siblings.
ALL_COMPETITOR_POIS_QUERY = text(
    """
    SELECT DISTINCT p.id      AS poi_id,
                    p.name    AS name,
                    ST_Y(p.geom) AS lat,
                    ST_X(p.geom) AS lng
    FROM pois p
    WHERE p.source = 'foursquare_os'
      AND p.geom IS NOT NULL
      AND jsonb_exists(p.metadata, 'fsq_category_labels')
      AND EXISTS (
          SELECT 1
          FROM jsonb_array_elements_text(
              (p.metadata->>'fsq_category_labels')::jsonb
          ) AS lbl
          WHERE lbl LIKE ANY(:like_patterns)
      )
    ORDER BY p.id
    """
)


def enumerate_all_competitor_pois() -> List[ResolvablePoi]:
    """Return every Competitor POI in the DB (any comune) as a ``ResolvablePoi`` the
    resolver can match — the worker's enumeration step. Prefixes are the union over all
    Vocazioni, so any comune a user later clicks is already covered."""
    prefixes = {prefix for prefixes in VOCAZIONE_COMPETITORS.values() for prefix in prefixes}
    like_patterns = [prefix + "%" for prefix in prefixes]
    with get_session_context() as session:
        rows = (
            session.execute(ALL_COMPETITOR_POIS_QUERY, {"like_patterns": like_patterns})
            .mappings()
            .all()
        )

    return [
        ResolvablePoi(
            poi_id=row["poi_id"],
            name=row["name"],
            lat=row["lat"],
            lng=row["lng"],
        )
        for row in rows
    ]
