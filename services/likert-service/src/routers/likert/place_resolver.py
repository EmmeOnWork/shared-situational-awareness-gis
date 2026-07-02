"""The resolve step — fill the permanent identity map (task 05; seed of the worker).

For each competitor POI: ask the ``google_client`` for candidates, run the pure
``place_matcher`` against them, and **upsert** the result into ``likert_poi_place`` —
a confident match (``google_place_id`` + confidence) or a recorded ``no_match`` so it
isn't re-resolved every cycle. This is the orchestration the background refresh
worker (task 06) drives; here it is callable on its own, over a comune's competitors,
so the identity map can be populated and inspected.

The decision lives in ``place_matcher`` (pure, tested in isolation) and the
persistence in ``place_repository``; this module only wires the two around the
(mockable) Google client — so the client and the SQL are manual-verify (PRD) while
the wiring is asserted over a fake client + patched upsert.
"""

from dataclasses import dataclass
from typing import List, Optional

from src.config import get_settings

from .place_matcher import match_place
from .place_repository import upsert_poi_place


@dataclass(frozen=True)
class ResolvablePoi:
    """A competitor POI to resolve: the monolith POI id (referenced by id only), its
    name and coordinates — the inputs the matcher needs. Enumerated from the shared
    DB by the caller (the enumeration SQL is manual-verify, like the sibling repos)."""

    poi_id: int
    name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class ResolveSummary:
    """An inspectable tally of a resolve run: how many POIs got a confident match
    and how many were recorded as no-match."""

    matched: int
    unmatched: int


def resolve_identities(
    pois: List[ResolvablePoi],
    *,
    client,
    max_distance_m: Optional[float] = None,
    min_name_similarity: Optional[float] = None,
) -> ResolveSummary:
    """Resolve each POI's Google identity and upsert it into the map.

    Args:
        pois: the competitor POIs to resolve (name + coordinates).
        client: the Google client (``find_candidates(name, lat, lng) -> [Candidate]``);
            injected so tests pass a fake and no live call is made.
        max_distance_m / min_name_similarity: the guardrail thresholds; default to the
            service settings.

    Returns:
        A ``ResolveSummary`` of matched vs unmatched, the run's inspectable result.
    """
    settings = get_settings()
    if max_distance_m is None:
        max_distance_m = settings.match_max_distance_m
    if min_name_similarity is None:
        min_name_similarity = settings.match_min_name_similarity

    matched = 0
    unmatched = 0
    for poi in pois:
        candidates = client.find_candidates(poi.name, poi.lat, poi.lng)
        match = match_place(
            poi.name,
            poi.lat,
            poi.lng,
            candidates,
            max_distance_m=max_distance_m,
            min_name_similarity=min_name_similarity,
        )
        if match is None:
            upsert_poi_place(
                poi.poi_id,
                google_place_id=None,
                match_confidence=None,
                no_match=True,
            )
            unmatched += 1
        else:
            upsert_poi_place(
                poi.poi_id,
                google_place_id=match.google_place_id,
                match_confidence=match.confidence,
                no_match=False,
            )
            matched += 1

    return ResolveSummary(matched=matched, unmatched=unmatched)
