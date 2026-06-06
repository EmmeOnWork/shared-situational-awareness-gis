from unittest.mock import MagicMock, patch

TERRITORIES = "/demographics/territories"

# Rows as the DB returns them: scale order (province -> region -> macro_area ->
# national), name-ordered within a level. The SQL ORDER BY does the sorting; the
# endpoint must carry that order through unchanged across all four levels.
ORDERED_ROWS = [
    {"territory_name": "Avellino", "level": "province"},
    {"territory_name": "Milano", "level": "province"},
    {"territory_name": "Lombardia", "level": "region"},
    {"territory_name": "Nord-ovest", "level": "macro_area"},
    {"territory_name": "Italia", "level": "national"},
]


def _patch_session_returning(rows):
    """Patch the router's session-context to yield a session whose query
    returns ``rows`` (mirrors the pollution router's test pattern)."""
    patcher = patch(
        "src.routers.demographics.demographics_router.get_session_context"
    )
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_territories_returns_ordered_name_level_list(client, auth_header):
    patcher = _patch_session_returning(ORDERED_ROWS)
    try:
        resp = client.get(TERRITORIES, headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.json() == [
        {"name": "Avellino", "level": "province"},
        {"name": "Milano", "level": "province"},
        {"name": "Lombardia", "level": "region"},
        {"name": "Nord-ovest", "level": "macro_area"},
        {"name": "Italia", "level": "national"},
    ]


def test_territories_requires_auth(client):
    """The route inherits the router-level demographics:read guard: no token ->
    401, never an unguarded listing."""
    resp = client.get(TERRITORIES)

    assert resp.status_code == 401
