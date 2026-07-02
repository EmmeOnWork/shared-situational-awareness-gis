"""The data route returns the tracer Gradimento payload.

This slice stubs the Gradimento (competitor/ratings resolution lands in later
slices), so we assert only the *contract shape* the widget renders against and
that the requested Vocazione is echoed — not specific data values, which are
placeholder and will change. The comune resolution is real now, so these tests
mock the resolver to a fixed comune (its own behaviour is covered by
``test_comune_resolver.py`` / ``test_comune_at_point.py``).
"""

from unittest.mock import patch

import pytest

from src.routers.likert.comune_resolver import Comune

GRADIMENTO = "/likert/gradimento"


@pytest.fixture(autouse=True)
def _resolved_comune():
    """Resolve every clicked point to a fixed comune AND default the competitor set
    and ratings cache to empty, so these tests exercise the route's contract
    independent of point-in-polygon resolution, the live competitor join and the
    ratings cache (each covered by its own module's tests). Tests that care about
    competitors/ratings re-patch ``find_competitors``/``fetch_ratings`` locally."""
    with patch(
        "src.routers.likert.likert_router.resolve_comune",
        return_value=Comune(region_id=42, name="Sant'Angelo dei Lombardi"),
    ), patch(
        "src.routers.likert.likert_router.find_competitors",
        return_value=[],
    ), patch(
        "src.routers.likert.likert_router.fetch_ratings",
        return_value={},
    ):
        yield


def test_gradimento_returns_the_contract_shape(client, auth_header):
    resp = client.get(
        GRADIMENTO,
        params={"lat": 40.9, "lng": 15.2, "vocazione": "dimora-del-benessere"},
        headers=auth_header(),
    )

    assert resp.status_code == 200
    body = resp.json()
    # The keys the <likert-widget> gauge + modal read (PRD API contract).
    assert set(body) >= {
        "comune",
        "vocazione",
        "status",
        "gradimento",
        "total_reviews",
        "n_competitors",
        "n_rated",
        "low_confidence",
        "updated_at",
        "breakdown",
    }


def test_gradimento_echoes_the_requested_vocazione(client, auth_header):
    """The slug from the bus is echoed back, so the widget can confirm the answer
    matches the Active Vocazione it asked about."""
    resp = client.get(
        GRADIMENTO,
        params={"lat": 40.9, "lng": 15.2, "vocazione": "atelier-di-ricordi"},
        headers=auth_header(),
    )

    assert resp.json()["vocazione"] == "atelier-di-ricordi"


# --- Acceptance: real Gradimento from the cached ratings (task 04) -------------
# The route now pools the cached online ratings of the comune's competitors into
# the real Gradimento. Driven over mocked ``find_competitors``/``fetch_ratings`` so
# we assert the assembled payload + states, not the SQL or the pooled-mean maths
# (covered by ``test_competitor_repository.py`` / ``test_ratings_repository.py`` /
# ``test_gradimento_calculator.py``).

from datetime import datetime, timezone  # noqa: E402

from src.routers.likert.competitor_repository import Competitor  # noqa: E402
from src.routers.likert.ratings_repository import PlaceRating  # noqa: E402

FETCHED = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _with_competitors_and_ratings(competitors, ratings):
    return (
        patch(
            "src.routers.likert.likert_router.find_competitors",
            return_value=competitors,
        ),
        patch(
            "src.routers.likert.likert_router.fetch_ratings",
            return_value=ratings,
        ),
    )


def test_ok_payload_carries_the_real_pooled_gradimento(client, auth_header):
    """Rated competitors ⇒ ``ok`` with the pooled-mean Gradimento, the review total,
    the rated count and the cache freshness — the numbers the gauge + modal read."""
    competitors = [
        Competitor(poi_id=11, name="Terme di Esempio", categoria="Spa"),
        Competitor(poi_id=22, name="Palestra Borgo", categoria="Gym"),
    ]
    ratings = {
        11: PlaceRating(poi_id=11, rating=4.6, n_ratings=120, fetched_at=FETCHED),
        22: PlaceRating(poi_id=22, rating=3.1, n_ratings=8, fetched_at=FETCHED),
    }
    p_comp, p_rate = _with_competitors_and_ratings(competitors, ratings)
    with p_comp, p_rate:
        resp = client.get(
            GRADIMENTO,
            params={"lat": 40.9, "lng": 15.2, "vocazione": "dimora-del-benessere"},
            headers=auth_header(),
        )

    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "ok"
    # (4.6·120 + 3.1·8) / 128 = 4.50625
    assert body["gradimento"] == pytest.approx(4.50625)
    assert body["total_reviews"] == 128
    assert body["n_competitors"] == 2
    assert body["n_rated"] == 2
    assert body["low_confidence"] is False
    assert body["updated_at"] == FETCHED.isoformat()


def test_breakdown_is_matched_rated_only_desc_by_reviews(client, auth_header):
    """The breakdown lists ONLY competitors with a confident match + rating, each
    with its ★ and review count, ordered by review count desc — an unmatched
    competitor is omitted (never shown as 0★, story 20)."""
    competitors = [
        Competitor(poi_id=11, name="Terme di Esempio", categoria="Spa"),
        Competitor(poi_id=22, name="Palestra Borgo", categoria="Gym"),
        Competitor(poi_id=33, name="Centro Senza Match", categoria="Spa"),
    ]
    ratings = {
        11: PlaceRating(poi_id=11, rating=4.6, n_ratings=8, fetched_at=FETCHED),
        22: PlaceRating(poi_id=22, rating=3.1, n_ratings=120, fetched_at=FETCHED),
    }
    p_comp, p_rate = _with_competitors_and_ratings(competitors, ratings)
    with p_comp, p_rate:
        resp = client.get(
            GRADIMENTO,
            params={"lat": 40.9, "lng": 15.2, "vocazione": "dimora-del-benessere"},
            headers=auth_header(),
        )

    breakdown = resp.json()["breakdown"]
    # 33 (no rating) omitted; 22 (120 reviews) before 11 (8 reviews).
    assert [row["poi_id"] for row in breakdown] == [22, 11]
    assert breakdown[0] == {
        "poi_id": 22,
        "name": "Palestra Borgo",
        "categoria": "Gym",
        "rating": 3.1,
        "n_ratings": 120,
    }


def test_thin_coverage_is_ok_but_low_confidence(client, auth_header):
    """Below the review FLOOR the needle is still shown (``ok`` + a value) but
    flagged ``low_confidence`` so the widget fades it and notes "pochi dati"."""
    competitors = [Competitor(poi_id=11, name="Terme di Esempio", categoria="Spa")]
    ratings = {
        11: PlaceRating(poi_id=11, rating=4.0, n_ratings=14, fetched_at=FETCHED)
    }
    p_comp, p_rate = _with_competitors_and_ratings(competitors, ratings)
    with p_comp, p_rate:
        resp = client.get(
            GRADIMENTO,
            params={"lat": 40.9, "lng": 15.2, "vocazione": "dimora-del-benessere"},
            headers=auth_header(),
        )

    body = resp.json()
    assert body["status"] == "ok"
    assert body["gradimento"] == pytest.approx(4.0)
    assert body["low_confidence"] is True


def test_competitors_found_but_none_rated_is_insufficient(client, auth_header):
    """Competitors exist but none has a cached rating ⇒ no signal: ``insufficient``,
    a null Gradimento and an empty breakdown (the widget shows "dati
    insufficienti"), while ``n_competitors`` still reports what was found."""
    competitors = [
        Competitor(poi_id=11, name="Terme di Esempio", categoria="Spa"),
        Competitor(poi_id=22, name="Palestra Borgo", categoria="Gym"),
    ]
    p_comp, p_rate = _with_competitors_and_ratings(competitors, {})
    with p_comp, p_rate:
        resp = client.get(
            GRADIMENTO,
            params={"lat": 40.9, "lng": 15.2, "vocazione": "dimora-del-benessere"},
            headers=auth_header(),
        )

    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "insufficient"
    assert body["gradimento"] is None
    assert body["n_competitors"] == 2
    assert body["n_rated"] == 0
    assert body["breakdown"] == []
    assert body["updated_at"] is None


def test_civic_vocazione_with_no_market_competitor_is_no_competitors(
    client, auth_header
):
    """A civic Vocazione (empty prefix map) has no genuine market competitor, so
    the route answers ``no_competitors`` and the widget shows "Nessun concorrente
    di mercato" — never a misleading empty needle."""
    with patch(
        "src.routers.likert.likert_router.find_competitors"
    ) as find_competitors:
        resp = client.get(
            GRADIMENTO,
            params={"lat": 40.9, "lng": 15.2, "vocazione": "vocazione-civica-senza-mercato"},
            headers=auth_header(),
        )

    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "no_competitors"
    assert body["n_competitors"] == 0
    assert body["breakdown"] == []
    # An empty prefix map means there is nothing to query — the repository is
    # never even hit.
    find_competitors.assert_not_called()
