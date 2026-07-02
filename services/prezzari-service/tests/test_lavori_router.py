"""The Lista B data route returns the real Prezzario dei Lavori payload.

Driven over a **mocked repository** (prior art likert ``test_gradimento_router.py``):
we assert the assembled contract shape the ``<prezzari-widget>`` right column renders
against and that the ``capitolo``/``q`` filter is forwarded to the repository — not the
SQL or the in-Python filtering (covered by ``test_prezzario_repository.py``) nor the
parse/curation (``test_prezzario_parser.py``). Region-fixed: takes no lat/lng.
"""

from unittest.mock import patch

from src.routers.prezzari.prezzario_repository import Capitolo, Voce

LAVORI = "/prezzari/lavori"

CAPITOLI = [
    Capitolo(codice="E.01", titolo="Demolizioni e rimozioni"),
    Capitolo(codice="E.21", titolo="Opere di recupero"),
]
VOCI = [
    Voce(
        codice="E.01.010.a",
        descrizione="Demolizione di tramezzatura in muratura",
        um="m²",
        prezzo=18.40,
        capitolo="E.01",
    ),
]


def _repo(capitoli=CAPITOLI, voci=VOCI, publication="2026"):
    """Patch the three repository seams the route reads, so the route's contract is
    exercised independent of the DB and the parser."""
    return (
        patch(
            "src.routers.prezzari.prezzari_router.current_publication",
            return_value=publication,
        ),
        patch(
            "src.routers.prezzari.prezzari_router.list_capitoli",
            return_value=capitoli,
        ),
        patch(
            "src.routers.prezzari.prezzari_router.find_voci",
            return_value=voci,
        ),
    )


def test_lavori_returns_publication_capitoli_and_voci(client, auth_header):
    """The right column reads publication (edition label), capitoli (nav) and voci
    (each codice/descrizione/um/prezzo/capitolo) from the curated snapshot."""
    p_pub, p_cap, p_voci = _repo()
    with p_pub, p_cap, p_voci:
        resp = client.get(LAVORI, headers=auth_header())

    assert resp.status_code == 200
    body = resp.json()
    assert body["publication"] == "2026"
    assert body["capitoli"] == [
        {"codice": "E.01", "titolo": "Demolizioni e rimozioni"},
        {"codice": "E.21", "titolo": "Opere di recupero"},
    ]
    assert body["voci"] == [
        {
            "codice": "E.01.010.a",
            "descrizione": "Demolizione di tramezzatura in muratura",
            "um": "m²",
            "prezzo": 18.40,
            "capitolo": "E.01",
        }
    ]


def test_lavori_forwards_capitolo_and_query_filter_to_the_repository(client, auth_header):
    """Capitolo nav + description search narrow the voci: the route forwards both to
    ``find_voci`` (the filtering itself is the repository's, unit-tested there)."""
    p_pub, p_cap, p_voci = _repo(voci=[])
    with p_pub, p_cap, p_voci as find_voci:
        resp = client.get(
            LAVORI,
            params={"capitolo": "E.21", "q": "recupero"},
            headers=auth_header(),
        )

    assert resp.status_code == 200
    find_voci.assert_called_once_with("E.21", "recupero")


def test_lavori_requires_a_jwt(client):
    """Both data routes are authentication-only: no bearer token ⇒ 401 (the bundle
    route stays unguarded; prior art likert ``test_auth.py``)."""
    resp = client.get(LAVORI)

    assert resp.status_code in (401, 403)
