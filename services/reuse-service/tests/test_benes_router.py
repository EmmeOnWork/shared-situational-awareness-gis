from unittest.mock import MagicMock, patch

BENES = "/reuse/benes"

# Rows as the join returns them: building_workshop ⋈ pois (by poi_id), already
# name-ordered by the SQL ORDER BY. lat/lng come from the POI geometry
# (ST_Y/ST_X of pois.geom) — the service owns no geometry of its own.
SEEDED_ROWS = [
    {"poi_id": 101, "name": "Ex Caserma", "lat": 40.9151, "lng": 15.4344},
    {"poi_id": 102, "name": "Palazzo Confiscato", "lat": 41.0073, "lng": 15.5021},
]


def _patch_session_returning(rows):
    """Patch the router's session-context to yield a session whose query
    returns ``rows`` (mirrors the demographic router's test pattern)."""
    patcher = patch("src.routers.benes.benes_router.get_session_context")
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = rows
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_benes_returns_seeded_bene_joined_to_poi(client, auth_header):
    """The toggle-list: each seeded Bene carried by its POI name + coords, in the
    {poiId, lat, lng, name} shape the Active Workshop bus (ADR-0003) consumes."""
    patcher = _patch_session_returning(SEEDED_ROWS)
    try:
        resp = client.get(BENES, headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.json() == [
        {"poiId": 101, "name": "Ex Caserma", "lat": 40.9151, "lng": 15.4344},
        {"poiId": 102, "name": "Palazzo Confiscato", "lat": 41.0073, "lng": 15.5021},
    ]


def test_benes_returns_empty_list_for_empty_registry(client, auth_header):
    """An empty ``building_workshop`` is a clean ``[]`` (200), not an error — the
    Selector simply shows no Bene yet."""
    patcher = _patch_session_returning([])
    try:
        resp = client.get(BENES, headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.json() == []


def test_benes_requires_auth(client):
    """The route inherits the router-level ``reuse:read`` guard: no token -> 401,
    never an unguarded listing of Bene."""
    resp = client.get(BENES)

    assert resp.status_code == 401
