"""The left-column route resolves the clicked point to a real comune.

Mirrors the demographic widget's ``test_at_point.py``: the route is driven over a
**mocked session**, so the real ``comune_resolver`` point-in-polygon logic runs
(route + resolver integrated) without a live database. A point inside a comune
echoes that comune in the ``/prezzari/locazione`` payload; a point in no comune (a
sea click or a click outside Campania) is a 404, which the left column renders as
its neutral "Clicca un comune della Campania" prompt rather than an error.

Only Lista A (left) depends on this input; Lista B (Lavori, region-fixed) is
untouched and keeps rendering from mount.
"""

from unittest.mock import MagicMock, patch

LOCAZIONE = "/prezzari/locazione"
LAVORI = "/prezzari/lavori"

# The comune polygon row as the shared ``areas`` join returns it: the monolith
# region id + its name (e.g. a click in Sant'Angelo dei Lombardi).
SANT_ANGELO_ROW = {"region_id": 42, "name": "Sant'Angelo dei Lombardi"}

# A click inside that comune.
INSIDE_PARAMS = {"lat": 40.9312, "lng": 15.1789}
# A click out at sea / outside Campania — no comune polygon contains it.
OFF_MAP_PARAMS = {"lat": 40.0, "lng": 17.5}


def _patch_resolver_session_with(row):
    """Patch the resolver's session-context so its point-in-polygon query returns
    ``row`` (a comune mapping, or ``None`` for an off-map click)."""
    patcher = patch("src.routers.prezzari.comune_resolver.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = row
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_point_inside_a_comune_echoes_that_comune(client, auth_header):
    patcher = _patch_resolver_session_with(SANT_ANGELO_ROW)
    # This test is about the resolver→route integration (the comune echoed back), so
    # the OMI read is stubbed out — its own read is covered by
    # ``test_locazione_router.py`` / ``test_locazione_repository.py``.
    with patch(
        "src.routers.prezzari.prezzari_router.find_locazione", return_value=[]
    ), patch(
        "src.routers.prezzari.prezzari_router.omi_publication", return_value=None
    ):
        try:
            resp = client.get(LOCAZIONE, params=INSIDE_PARAMS, headers=auth_header())
        finally:
            patcher.stop()

    assert resp.status_code == 200
    comune = resp.json()["comune"]
    assert comune["region_id"] == 42
    assert comune["name"] == "Sant'Angelo dei Lombardi"


def test_point_in_no_comune_is_404(client, auth_header):
    patcher = _patch_resolver_session_with(None)
    try:
        resp = client.get(LOCAZIONE, params=OFF_MAP_PARAMS, headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 404


def test_off_map_click_leaves_the_right_column_unaffected(client, auth_header):
    """Lista B (Lavori) is region-fixed: an off-map click that 404s the left list
    must not touch the right list — it still answers 200 from the regional snapshot.
    The snapshot is served over a mocked repository (no live DB); its real read is
    covered by ``test_lavori_router.py`` / ``test_prezzario_repository.py``."""
    from src.routers.prezzari.prezzario_repository import Voce

    voci = [Voce(codice="E.01.010.a", descrizione="Demolizione", um="m²",
                 prezzo=18.40, capitolo="E.01")]
    with patch(
        "src.routers.prezzari.prezzari_router.current_publication", return_value="2026"
    ), patch(
        "src.routers.prezzari.prezzari_router.list_capitoli", return_value=[]
    ), patch(
        "src.routers.prezzari.prezzari_router.find_voci", return_value=voci
    ):
        resp = client.get(LAVORI, headers=auth_header())
    assert resp.status_code == 200
    assert resp.json()["voci"]
