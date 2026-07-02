"""I Prezziari data routes — the two reference price lists.

The left list (Prezziario di Locazione) resolves the clicked point to a REAL comune
(its Zone OMI rows stay stubbed until a later slice); the right list (Prezzario dei
Lavori) reads the **real** curated snapshot through ``prezzario_repository``. Both
routes are authentication-only. The left-column tests drive the route over a
**mocked** resolver session (point-in-polygon without a live DB); the right list is
driven over a **mocked** repository (its own behaviour is covered by
``test_lavori_router.py`` / ``test_prezzario_repository.py``).
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from src.routers.prezzari.locazione_repository import ZonaOmi
from src.routers.prezzari.prezzario_repository import Capitolo, Voce

LOCAZIONE = "/prezzari/locazione"
LAVORI = "/prezzari/lavori"

# A minimal OMI snapshot the mocked repository serves for the left-list leg.
LOCAZIONE_ZONE = [
    ZonaOmi(zona="B1", tipologia="Abitazioni civili", stato="Normale",
            canone_min=3.2, canone_max=4.5, um="€/m²/mese"),
]

# A comune polygon row as the shared ``areas`` join returns it (region id + name).
COMUNE_ROW = {"region_id": 15, "name": "Avellino"}

# A minimal curated snapshot the mocked repository serves for the right-list leg.
LAVORI_CAPITOLI = [Capitolo(codice="E.01", titolo="Demolizioni e rimozioni")]
LAVORI_VOCI = [
    Voce(codice="E.01.010.a", descrizione="Demolizione di tramezzatura",
         um="m²", prezzo=18.40, capitolo="E.01"),
]


def _patch_resolver_session_with(row):
    """Patch the resolver's session-context so its point-in-polygon query returns
    ``row`` — lets the left route resolve a comune without a live database."""
    patcher = patch("src.routers.prezzari.comune_resolver.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = row
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def _mock_locazione_repository():
    """Serve the left list's OMI rows from a fixed snapshot (no live DB); the resolver
    still runs over its own mocked session."""
    stack = ExitStack()
    stack.enter_context(patch(
        "src.routers.prezzari.prezzari_router.omi_publication", return_value="2025 · II semestre"))
    stack.enter_context(patch(
        "src.routers.prezzari.prezzari_router.find_locazione", return_value=LOCAZIONE_ZONE))
    return stack


def _mock_lavori_repository():
    """Serve the right list from a fixed curated snapshot (no live DB)."""
    stack = ExitStack()
    stack.enter_context(patch(
        "src.routers.prezzari.prezzari_router.current_publication", return_value="2026"))
    stack.enter_context(patch(
        "src.routers.prezzari.prezzari_router.list_capitoli", return_value=LAVORI_CAPITOLI))
    stack.enter_context(patch(
        "src.routers.prezzari.prezzari_router.find_voci", return_value=LAVORI_VOCI))
    return stack


# --- Acceptance test (outer tracer bullet) --------------------------------
def test_both_lists_answer_in_contract_shape_when_authenticated(client, auth_header):
    """The whole data plane end-to-end: with a valid JWT, the left list
    (Prezziario di Locazione, comune-scoped) and the right list (Prezzario dei
    Lavori, region-fixed) each answer 200 in their PRD contract shape."""
    patcher = _patch_resolver_session_with(COMUNE_ROW)
    try:
        with _mock_locazione_repository():
            loc = client.get(
                LOCAZIONE, params={"lat": 40.9, "lng": 14.8}, headers=auth_header()
            )
    finally:
        patcher.stop()
    assert loc.status_code == 200
    loc_body = loc.json()
    assert set(loc_body) >= {"comune", "publication", "zone"}
    assert set(loc_body["comune"]) >= {"region_id", "name"}
    assert isinstance(loc_body["zone"], list)

    with _mock_lavori_repository():
        lav = client.get(LAVORI, headers=auth_header())
    assert lav.status_code == 200
    lav_body = lav.json()
    assert set(lav_body) >= {"publication", "capitoli", "voci"}
    assert isinstance(lav_body["capitoli"], list)
    assert isinstance(lav_body["voci"], list)


# Both per-list contracts are now owned by the dedicated route tests over real routes +
# mocked repositories: the Prezziario di Locazione (left) by ``test_locazione_router.py``
# and the Prezzario dei Lavori (right) by ``test_lavori_router.py``. The stub-shape
# assertions that once lived here are retired — this file keeps only the end-to-end
# tracer that both lists answer together in contract shape.
