"""The data route resolves the clicked point to a real comune.

Mirrors the demographic widget's ``test_at_point.py``: the route is driven over a
**mocked session**, so the real ``comune_resolver`` point-in-polygon logic runs
(route + resolver integrated) without a live database. A point inside a comune
echoes that comune in the payload; a point in no comune (a sea click) is a 404,
which the widget renders as a graceful empty state.
"""

from unittest.mock import MagicMock, patch

GRADIMENTO = "/likert/gradimento"

# The comune polygon row as the shared ``areas`` join returns it: the monolith
# region id + its name (e.g. a click in Sant'Angelo dei Lombardi).
SANT_ANGELO_ROW = {"region_id": 42, "name": "Sant'Angelo dei Lombardi"}

# A click inside that comune.
INSIDE_PARAMS = {"lat": 40.9312, "lng": 15.1789, "vocazione": "dimora-del-benessere"}
# A click out at sea — no comune polygon contains it.
SEA_PARAMS = {"lat": 40.0, "lng": 17.5, "vocazione": "dimora-del-benessere"}


def _patch_resolver_session_with(row):
    """Patch the resolver's session-context so its point-in-polygon query returns
    ``row`` (a comune mapping, or ``None`` for an off-map click)."""
    patcher = patch("src.routers.likert.comune_resolver.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = row
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_point_inside_a_comune_echoes_that_comune(client, auth_header):
    patcher = _patch_resolver_session_with(SANT_ANGELO_ROW)
    # Stub the competitor join: this test is about comune echo, not competitors.
    competitors = patch(
        "src.routers.likert.likert_router.find_competitors", return_value=[]
    )
    competitors.start()
    try:
        resp = client.get(GRADIMENTO, params=INSIDE_PARAMS, headers=auth_header())
    finally:
        patcher.stop()
        competitors.stop()

    assert resp.status_code == 200
    comune = resp.json()["comune"]
    assert comune["region_id"] == 42
    assert comune["name"] == "Sant'Angelo dei Lombardi"


def test_point_in_no_comune_is_404(client, auth_header):
    patcher = _patch_resolver_session_with(None)
    try:
        resp = client.get(GRADIMENTO, params=SEA_PARAMS, headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 404
