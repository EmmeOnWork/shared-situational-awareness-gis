"""The Lista A data route returns the real Prezziario di Locazione (OMI) payload.

Driven over a **mocked repository + mocked resolver** (prior art likert
``test_gradimento_router.py``, demographic ``test_at_point.py``): we assert the
assembled contract shape the ``<prezzari-widget>`` left column renders against — the
resolved comune, the OMI ``publication`` label and the ``zone`` rows — plus the
degradation contract (empty ``zone`` for a comune without OMI, 404 for a point in no
comune, 401 without a JWT). NOT the SQL (``test_locazione_repository.py``) nor the
parse/curation (``test_omi_parser.py``). Comune-scoped: takes lat/lng.
"""

from unittest.mock import MagicMock, patch

from src.routers.prezzari.locazione_repository import ZonaOmi

LOCAZIONE = "/prezzari/locazione"

# A comune polygon row as the shared ``areas`` join returns it (region id + name).
COMUNE_ROW = {"region_id": 15, "name": "Avellino"}

# The comune's OMI rows as the repository serves them (already region-scoped).
ZONE = [
    ZonaOmi(zona="B1", tipologia="Abitazioni civili", stato="Normale",
            canone_min=3.2, canone_max=4.5, um="€/m²/mese"),
    ZonaOmi(zona="C2", tipologia="Abitazioni civili", stato="Scadente",
            canone_min=2.1, canone_max=3.0, um="€/m²/mese"),
]


def _patch_resolver_session_with(row):
    """Patch the resolver's session-context so its point-in-polygon query returns
    ``row`` — lets the route resolve a comune without a live database."""
    patcher = patch("src.routers.prezzari.comune_resolver.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = row
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def _repo(zone=ZONE, publication="2025 · II semestre"):
    """Patch the two OMI repository seams the route reads, so the route's contract is
    exercised independent of the DB and the parser."""
    return (
        patch("src.routers.prezzari.prezzari_router.find_locazione", return_value=zone),
        patch("src.routers.prezzari.prezzari_router.omi_publication", return_value=publication),
    )


# --- Acceptance test (outer tracer bullet) --------------------------------
def test_locazione_returns_publication_and_zone_for_a_comune_with_omi(client, auth_header):
    """With a valid JWT and a point inside a Campania comune, the left list answers
    200 with the resolved comune, the OMI publication label and its Zone OMI rows
    (each zona/tipologia/stato/min–max canone/um) — the PRD Lista A contract."""
    resolver = _patch_resolver_session_with(COMUNE_ROW)
    p_find, p_pub = _repo()
    try:
        with p_find as find_locazione, p_pub:
            resp = client.get(
                LOCAZIONE, params={"lat": 40.9, "lng": 14.8}, headers=auth_header()
            )
    finally:
        resolver.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["comune"] == {"region_id": 15, "name": "Avellino"}
    assert body["publication"] == "2025 · II semestre"
    assert body["zone"] == [
        {"zona": "B1", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": 3.2, "canone_max": 4.5, "um": "€/m²/mese"},
        {"zona": "C2", "tipologia": "Abitazioni civili", "stato": "Scadente",
         "canone_min": 2.1, "canone_max": 3.0, "um": "€/m²/mese"},
    ]
    # The comune is resolved once and forwarded to the repository by region id.
    find_locazione.assert_called_once_with(15)


def test_locazione_empty_zone_for_a_comune_without_omi(client, auth_header):
    """A resolved comune with no published OMI answers 200 with an empty ``zone`` (the
    widget renders "quotazioni OMI non disponibili"), independent of the right list."""
    resolver = _patch_resolver_session_with(COMUNE_ROW)
    p_find, p_pub = _repo(zone=[], publication=None)
    try:
        with p_find, p_pub:
            resp = client.get(
                LOCAZIONE, params={"lat": 40.9, "lng": 14.8}, headers=auth_header()
            )
    finally:
        resolver.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["comune"] == {"region_id": 15, "name": "Avellino"}
    assert body["zone"] == []


def test_locazione_point_in_no_comune_is_404(client, auth_header):
    """A click in no comune (sea / outside Campania) resolves to nothing → 404, which
    the left column renders as its neutral prompt (prior art demographic
    ``test_at_point.py``)."""
    resolver = _patch_resolver_session_with(None)
    try:
        resp = client.get(
            LOCAZIONE, params={"lat": 0.0, "lng": 0.0}, headers=auth_header()
        )
    finally:
        resolver.stop()

    assert resp.status_code == 404


def test_locazione_requires_a_jwt(client):
    """Both data routes are authentication-only: no bearer token ⇒ 401/403."""
    resp = client.get(LOCAZIONE, params={"lat": 40.9, "lng": 14.8})

    assert resp.status_code in (401, 403)
