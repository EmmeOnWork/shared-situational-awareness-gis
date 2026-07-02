"""Fuzzy POI → Google place matching (pure core) — PRD "Competitor resolution";
service ADR-0001.

Our POIs are foursquare-native; Google has no shared key, so we resolve identity by
**name + coordinates**: given a POI and a list of Google candidates, return the best
``google_place_id`` within a distance + name-similarity threshold, or ``None`` when
nothing is confident enough. ``None`` is the **"exclude on no confident match"**
guardrail (ADR-0001 consequence): never attach a wrong rating; an unmatched
competitor simply doesn't contribute to the Gradimento.

No IO, no DB, no HTTP — the candidates are produced by the ``google_client`` adapter
and fed in, so this decision is tested in isolation. Distance is haversine; name
similarity is stdlib ``difflib`` on normalised names.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt
from typing import List, Optional

#: Mean Earth radius in metres (haversine).
_EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class Candidate:
    """A Google place candidate as the ``google_client`` adapter returns it: the
    permanent ``google_place_id`` plus the name + coordinates we match against."""

    google_place_id: str
    name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class PlaceMatch:
    """The chosen identity: the resolved ``google_place_id`` and a ``confidence`` —
    the name-similarity score [0,1] of the picked candidate, stored as
    ``match_confidence`` and inspectable in the identity map."""

    google_place_id: str
    confidence: float


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS84 points, in metres."""
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * asin(sqrt(a))


def _name_similarity(a: str, b: str) -> float:
    """A [0,1] similarity of two place names, case/space-insensitive."""
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def match_place(
    poi_name: str,
    poi_lat: float,
    poi_lng: float,
    candidates: List[Candidate],
    *,
    max_distance_m: float,
    min_name_similarity: float,
) -> Optional[PlaceMatch]:
    """Return the most confident Google match for a POI, or ``None`` when none clears
    both thresholds.

    Among candidates within ``max_distance_m`` **and** at least ``min_name_similarity``
    similar by name, pick the **nearest**; a tie in distance is broken by the higher
    name similarity. The match's ``confidence`` is the chosen candidate's name
    similarity. ``None`` (empty list, all too far, or all too dissimilar) is the
    guardrail to exclude the competitor rather than mis-pair it.
    """
    qualifying = []
    for candidate in candidates:
        distance = _haversine_m(poi_lat, poi_lng, candidate.lat, candidate.lng)
        if distance > max_distance_m:
            continue
        similarity = _name_similarity(poi_name, candidate.name)
        if similarity < min_name_similarity:
            continue
        qualifying.append((distance, similarity, candidate))

    if not qualifying:
        return None

    # Nearest first; ties broken by the more similar name (so confidence is highest
    # among the equally-close).
    _distance, similarity, best = min(qualifying, key=lambda q: (q[0], -q[1]))
    return PlaceMatch(google_place_id=best.google_place_id, confidence=similarity)
