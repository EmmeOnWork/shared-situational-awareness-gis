"""Both I Prezziari data routes are authentication-only: a valid monolith JWT is
required (no special scope), while the bundle route stays open. The guard is the
copied verify (src/security) applied as a group in src/app.py.
"""

from unittest.mock import MagicMock, patch

import pytest

GUARDED = [
    ("/prezzari/locazione", {"lat": 40.9, "lng": 14.8}),
    ("/prezzari/lavori", {}),
]


@pytest.mark.parametrize("path,params", GUARDED)
def test_data_route_requires_a_token(client, path, params):
    """No Authorization header → 401 (the guarded surface is explicit)."""
    resp = client.get(path, params=params)

    assert resp.status_code == 401


@pytest.mark.parametrize("path,params", GUARDED)
def test_data_route_rejects_an_invalid_token(client, path, params):
    """A garbage bearer token cannot be verified → 401 (not 200, not 500)."""
    resp = client.get(path, params=params, headers={"Authorization": "Bearer not.a.jwt"})

    assert resp.status_code == 401


@pytest.mark.parametrize("path,params", GUARDED)
def test_data_route_accepts_a_valid_token_without_any_scope(
    client, auth_header, path, params
):
    """A valid access token with an EMPTY scope is enough — any logged-in user may
    consult these public reference lists (auth-only, no scope)."""
    # Keep this a pure auth check (valid token → 200, not a DB round-trip): mock the
    # left route's resolver session AND the right route's repository so neither hits a
    # live DB. Each set of patches is inert for the other route.
    session = patch("src.routers.prezzari.comune_resolver.get_session_context")
    mock_get_session = session.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = {
        "region_id": 15,
        "name": "Avellino",
    }
    mock_get_session.return_value.__enter__.return_value = mock_session
    repo = [
        patch("src.routers.prezzari.prezzari_router.current_publication", return_value="2026"),
        patch("src.routers.prezzari.prezzari_router.list_capitoli", return_value=[]),
        patch("src.routers.prezzari.prezzari_router.find_voci", return_value=[]),
        patch("src.routers.prezzari.prezzari_router.omi_publication", return_value="2025 · II semestre"),
        patch("src.routers.prezzari.prezzari_router.find_locazione", return_value=[]),
    ]
    for p in repo:
        p.start()
    try:
        resp = client.get(path, params=params, headers=auth_header())
    finally:
        session.stop()
        for p in repo:
            p.stop()

    assert resp.status_code == 200
