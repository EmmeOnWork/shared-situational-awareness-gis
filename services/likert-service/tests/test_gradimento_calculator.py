"""Unit tests for the pure Gradimento calculator (PRD "The Gradimento"; ADR-0001).

Pure-function-in-isolation style (cf. round-service ``test_consensus.py``): no
TestClient, no DB — feed the rated competitor places, assert the pooled-mean
weighting and the server-decided states. The ``no_competitors`` state is the
router's call (an empty Vocazione prefix map), NOT the calculator's; the
calculator only ever sees the rated set and decides ``ok`` vs ``insufficient`` and
the low-confidence flag.
"""

import pytest

from src.routers.likert.gradimento_calculator import (
    FLOOR,
    RatedPlace,
    compute_gradimento,
)


def test_pooled_mean_weights_each_review_once():
    """Gradimento = Σ(ratingᵢ·nᵢ)/Σnᵢ — a worked fixture: 5★×100 + 3★×300 over 400
    reviews = 3.5, not the unweighted 4.0. Each review counts once."""
    res = compute_gradimento(
        [RatedPlace(rating=5.0, n_ratings=100), RatedPlace(rating=3.0, n_ratings=300)]
    )

    assert res.status == "ok"
    assert res.value == pytest.approx(3.5)
    assert res.total_reviews == 400
    assert res.n_rated == 2
    assert res.low_confidence is False


def test_a_busier_competitor_weighs_more_than_a_quiet_one():
    """The weighting is by review count, so a 1★ place with 99 reviews drags the
    pooled mean far below the unweighted average of a 5★ place with a single one."""
    res = compute_gradimento(
        [RatedPlace(rating=5.0, n_ratings=1), RatedPlace(rating=1.0, n_ratings=99)]
    )

    # (5·1 + 1·99)/100 = 1.04, nowhere near the unweighted 3.0.
    assert res.value == pytest.approx(1.04)


def test_zero_rated_competitors_is_insufficient_with_no_value():
    """No rated competitor (e.g. all unrated, or none confidently matched) ⇒ there
    is no signal: status ``insufficient`` and a null Gradimento (the widget shows
    "dati insufficienti", no needle), never a fabricated 0★."""
    res = compute_gradimento([])

    assert res.status == "insufficient"
    assert res.value is None
    assert res.total_reviews == 0
    assert res.n_rated == 0
    assert res.low_confidence is False


def test_thin_coverage_below_the_floor_is_low_confidence():
    """Competitors are rated but the pooled review count is below FLOOR (15): the
    needle is shown (status ``ok``, a real value) but flagged low-confidence so the
    widget fades it and appends "pochi dati"."""
    res = compute_gradimento([RatedPlace(rating=4.0, n_ratings=14)])

    assert res.status == "ok"
    assert res.value == pytest.approx(4.0)
    assert res.low_confidence is True


def test_exactly_at_the_floor_is_confident():
    """The FLOOR is the threshold: total reviews == FLOOR is enough ⇒ not
    low-confidence (boundary inclusive)."""
    res = compute_gradimento([RatedPlace(rating=4.0, n_ratings=FLOOR)])

    assert res.low_confidence is False


def test_a_single_rated_competitor_is_its_own_average():
    """One rated competitor: the pooled mean is just that place's average."""
    res = compute_gradimento([RatedPlace(rating=4.2, n_ratings=50)])

    assert res.status == "ok"
    assert res.value == pytest.approx(4.2)
    assert res.n_rated == 1
