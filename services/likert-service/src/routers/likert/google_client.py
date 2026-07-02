"""Thin Google Places adapter — the only place that talks to Google over HTTP.

Isolated on purpose (PRD; ADR-0001): the matching *decision* is the pure
``place_matcher`` and the orchestration is ``place_resolver``, both tested without a
network; this adapter just turns a POI's name + coordinates into a list of
``Candidate`` records. It is **manual-verify** (no automated test) — exercised
through the resolver/worker with the client mocked, and against the live API by hand.

The widget **never** calls Google: only the server-side resolve step and refresh
worker do. The API key comes from settings (``GOOGLE_API_KEY``).
"""

from typing import List, Tuple

import httpx

from src.config import get_settings

from .place_matcher import Candidate

# Find Place from Text: the cheapest way to turn "name near (lat,lng)" into candidate
# places with the id + coordinates the matcher needs. Biased to a tight radius around
# the POI so candidates are local; the matcher then enforces the distance threshold.
_FIND_PLACE_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
# Place Details: the rating + review count for an already-resolved place — the two
# numbers the refresh worker caches per place per TTL cycle.
_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
_LOCATION_BIAS_RADIUS_M = 2000
_TIMEOUT_S = 10.0


class GoogleClient:
    """Find Google place candidates for a POI. One instance per resolve/worker run."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key or get_settings().google_api_key

    def find_candidates(self, name: str, lat: float, lng: float) -> List[Candidate]:
        """Return Google candidates for ``name`` near ``(lat, lng)``; an empty list
        when Google has nothing (the resolver records that POI as ``no_match``)."""
        params = {
            "input": name,
            "inputtype": "textquery",
            "fields": "place_id,name,geometry",
            "locationbias": f"circle:{_LOCATION_BIAS_RADIUS_M}@{lat},{lng}",
            "key": self._api_key,
        }
        response = httpx.get(_FIND_PLACE_URL, params=params, timeout=_TIMEOUT_S)
        response.raise_for_status()
        payload = response.json()

        candidates = []
        for c in payload.get("candidates", []):
            location = c.get("geometry", {}).get("location", {})
            place_id = c.get("place_id")
            if place_id is None or "lat" not in location or "lng" not in location:
                continue
            candidates.append(
                Candidate(
                    google_place_id=place_id,
                    name=c.get("name", ""),
                    lat=location["lat"],
                    lng=location["lng"],
                )
            )
        return candidates

    def fetch_place_rating(self, google_place_id: str) -> Tuple[float, int]:
        """Return ``(rating, user_ratings_total)`` for a resolved place — the worker's
        per-TTL refresh call. A place Google has no rating for yields ``(0.0, 0)`` (it
        simply doesn't contribute to any Gradimento). Only the worker calls this; the
        widget always reads the cache."""
        params = {
            "place_id": google_place_id,
            "fields": "rating,user_ratings_total",
            "key": self._api_key,
        }
        response = httpx.get(_DETAILS_URL, params=params, timeout=_TIMEOUT_S)
        response.raise_for_status()
        result = response.json().get("result", {})
        return float(result.get("rating", 0.0)), int(result.get("user_ratings_total", 0))
