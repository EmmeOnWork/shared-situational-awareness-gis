"""Unit tests for the pure place matcher (Tier-2 guardrail; PRD; ADR-0001).

Pure-function-in-isolation style (cf. ``test_gradimento_calculator``): no client,
no DB — feed a POI (name + coordinates) and a list of Google candidates, assert the
chosen ``google_place_id`` (+confidence) or ``None``. This is the "exclude on no
confident match" guardrail: a competitor with no confident match must return None so
it never attaches a wrong rating.
"""

import pytest

from src.routers.likert.place_matcher import Candidate, match_place

# Thresholds the resolver will pass in from config; pinned here so the tests state
# the decision boundary explicitly.
MAX_DISTANCE_M = 150
MIN_NAME_SIMILARITY = 0.6


def test_picks_the_only_candidate_within_both_thresholds():
    """A candidate with the same name a few metres away is a confident match: its
    place id comes back, flagged with a confidence in (0, 1]."""
    candidates = [
        Candidate(
            google_place_id="g-spa", name="Terme di Esempio", lat=40.9301, lng=15.1701
        )
    ]

    match = match_place(
        "Terme di Esempio",
        40.93,
        15.17,
        candidates,
        max_distance_m=MAX_DISTANCE_M,
        min_name_similarity=MIN_NAME_SIMILARITY,
    )

    assert match is not None
    assert match.google_place_id == "g-spa"
    assert 0 < match.confidence <= 1


def test_a_same_named_but_too_far_candidate_is_no_match():
    """Right name, wrong place: a candidate ~5 km away is beyond the distance
    threshold, so it is excluded (None) rather than mis-paired — the guardrail
    against attaching a different town's place."""
    candidates = [
        Candidate(
            google_place_id="g-far", name="Terme di Esempio", lat=40.98, lng=15.17
        )
    ]

    match = match_place(
        "Terme di Esempio",
        40.93,
        15.17,
        candidates,
        max_distance_m=MAX_DISTANCE_M,
        min_name_similarity=MIN_NAME_SIMILARITY,
    )

    assert match is None


def test_a_nearby_but_differently_named_candidate_is_no_match():
    """Same spot, unrelated name: a candidate at the exact coordinates but with a
    name nothing like the POI falls below the name-similarity threshold, so it is
    excluded — coordinates alone are not enough to claim identity."""
    candidates = [
        Candidate(
            google_place_id="g-other", name="Officina Meccanica Rossi", lat=40.93, lng=15.17
        )
    ]

    match = match_place(
        "Terme di Esempio",
        40.93,
        15.17,
        candidates,
        max_distance_m=MAX_DISTANCE_M,
        min_name_similarity=MIN_NAME_SIMILARITY,
    )

    assert match is None


def test_empty_candidate_list_is_no_match():
    """Google returned nothing for this POI: no place to attach, so None (the
    resolver records this as ``no_match``)."""
    match = match_place(
        "Terme di Esempio",
        40.93,
        15.17,
        [],
        max_distance_m=MAX_DISTANCE_M,
        min_name_similarity=MIN_NAME_SIMILARITY,
    )

    assert match is None


def test_picks_the_nearest_when_several_clear_both_thresholds():
    """Two equally-named candidates both inside the thresholds: the nearer one wins,
    regardless of list order (the farther one is listed first)."""
    candidates = [
        Candidate(
            google_place_id="g-far", name="Terme di Esempio", lat=40.9309, lng=15.17
        ),  # ~100 m
        Candidate(
            google_place_id="g-near", name="Terme di Esempio", lat=40.9301, lng=15.17
        ),  # ~11 m
    ]

    match = match_place(
        "Terme di Esempio",
        40.93,
        15.17,
        candidates,
        max_distance_m=MAX_DISTANCE_M,
        min_name_similarity=MIN_NAME_SIMILARITY,
    )

    assert match is not None
    assert match.google_place_id == "g-near"


def test_a_tie_in_distance_is_broken_by_name_similarity():
    """Two candidates at the same point: the one whose name is closer to the POI's
    wins (and its higher similarity becomes the confidence)."""
    candidates = [
        Candidate(
            google_place_id="g-loose", name="Terme Esempio Centro", lat=40.93, lng=15.17
        ),
        Candidate(
            google_place_id="g-exact", name="Terme di Esempio", lat=40.93, lng=15.17
        ),
    ]

    match = match_place(
        "Terme di Esempio",
        40.93,
        15.17,
        candidates,
        max_distance_m=MAX_DISTANCE_M,
        min_name_similarity=MIN_NAME_SIMILARITY,
    )

    assert match is not None
    assert match.google_place_id == "g-exact"
    assert match.confidence == pytest.approx(1.0)
