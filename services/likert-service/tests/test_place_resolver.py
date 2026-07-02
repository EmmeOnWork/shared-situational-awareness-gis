"""Acceptance test for the resolve step — the seed of the refresh worker (task 05).

Outer (double-loop) gate: drive ``resolve_identities`` over an **injected fake
Google client** (no live calls) and a **patched upsert**, and assert what lands in
the permanent identity map ``likert_poi_place``. The matching *decision* is the pure
``place_matcher``'s job (tested in isolation in ``test_place_matcher``); here we
assert the orchestration's observable effect: a confident match persists the
``google_place_id`` (+confidence, ``no_match=false``); no confident match persists
``no_match=true`` so it isn't re-resolved every cycle; and the run returns an
inspectable summary.

The ``google_client`` HTTP adapter and the upsert SQL are manual-verify (PRD), so
the client is a stand-in and the persistence seam is patched.
"""

from unittest.mock import patch

from src.routers.likert.place_matcher import Candidate
from src.routers.likert.place_resolver import ResolvablePoi, resolve_identities


class FakeGoogleClient:
    """Stands in for ``google_client``: returns canned candidates per POI name, so
    the resolver runs without a live Google call (PRD: no live calls in tests)."""

    def __init__(self, candidates_by_name):
        self._candidates_by_name = candidates_by_name
        self.calls = []

    def find_candidates(self, name, lat, lng):
        self.calls.append((name, lat, lng))
        return self._candidates_by_name.get(name, [])


# A spa POI with a near, same-named Google candidate (confident), and a clinic POI
# whose only candidate is far away (no confident match → excluded).
SPA = ResolvablePoi(poi_id=11, name="Terme di Esempio", lat=40.93, lng=15.17)
CLINIC = ResolvablePoi(poi_id=22, name="Studio Medico Borgo", lat=40.93, lng=15.17)

CANDIDATES = {
    "Terme di Esempio": [
        Candidate(
            google_place_id="g-spa", name="Terme di Esempio", lat=40.9301, lng=15.1701
        )
    ],
    # ~5 km away: outside the distance threshold, so not a confident match.
    "Studio Medico Borgo": [
        Candidate(
            google_place_id="g-far", name="Studio Medico Borgo", lat=40.98, lng=15.17
        )
    ],
}


def test_confident_match_persists_place_id_and_no_match_records_the_rest():
    client = FakeGoogleClient(CANDIDATES)

    with patch("src.routers.likert.place_resolver.upsert_poi_place") as upsert:
        summary = resolve_identities([SPA, CLINIC], client=client)

    calls = {c.args[0]: c.kwargs for c in upsert.call_args_list}

    # Confident match → google_place_id + confidence, not flagged no_match.
    assert calls[11]["google_place_id"] == "g-spa"
    assert calls[11]["no_match"] is False
    assert calls[11]["match_confidence"] is not None

    # No confident match → recorded as no_match so the worker won't re-resolve it
    # every cycle, and never attaches a wrong place id.
    assert calls[22]["google_place_id"] is None
    assert calls[22]["no_match"] is True

    # The run is inspectable.
    assert summary.matched == 1
    assert summary.unmatched == 1
