from unittest.mock import MagicMock, patch

AT_POINT = "/demographics/at-point"

# A wide demographic row as the shared table stores it (province scale).
AVELLINO_ROW = {
    "territory_name": "Avellino",
    "territory_name_istat": "Avellino",
    "level": "province",
    "pop_total": 411.0,
    "pop_italian": 396.0,
    "pop_foreign": 15.0,
    "age_share_0_14": 11.8,
    "age_share_15_64": 62.4,
    "age_share_65_plus": 25.8,
    "mig_rate_internal": -4.1,
    "mig_rate_foreign": 3.2,
    "mig_rate_total": -0.9,
}

ITALIA_ROW = {**AVELLINO_ROW, "territory_name": "Italia", "level": "national"}

# A click inside the province of Avellino (≈ the comune of Calitri), which the
# demographic data does NOT carry — the whole point of resolving by geometry.
CALITRI_POINT = f"{AT_POINT}?lat=40.9012&lng=15.4344"


def _patch_session_with(side_effect):
    """Patch the router's session-context so successive ``.mappings().first()``
    calls return the given sequence (one per query the endpoint runs)."""
    patcher = patch(
        "src.routers.demographics.demographics_router.get_session_context"
    )
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.side_effect = (
        side_effect
    )
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_at_point_inside_province_returns_that_profile(client, auth_header):
    """A click in a comune resolves to the containing province's profile —
    Calitri's point comes back as Avellino (the first/spatial query hits)."""
    patcher = _patch_session_with([AVELLINO_ROW])
    try:
        resp = client.get(CALITRI_POINT, headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "Avellino"
    assert body["metadata"]["territory_name"] == "Avellino"
    assert body["metadata"]["level"] == "province"


def test_at_point_outside_all_provinces_falls_back_to_national(client, auth_header):
    """No province contains the point (e.g. a click at sea) but boundaries ARE
    loaded -> national fallback: spatial miss, table non-empty, national hit."""
    patcher = _patch_session_with([None, {"one": 1}, ITALIA_ROW])
    try:
        resp = client.get(f"{AT_POINT}?lat=42.0&lng=12.0", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.json()["metadata"]["level"] == "national"


def test_at_point_without_boundaries_is_503(client, auth_header):
    """Until the boundary table is seeded, the spatial query misses AND the table
    is empty -> 503, so the widget degrades to its manual picker rather than
    reading it as 'no data'."""
    patcher = _patch_session_with([None, None])
    try:
        resp = client.get(CALITRI_POINT, headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 503


def test_at_point_missing_coords_is_422(client, auth_header):
    """``lat``/``lng`` are required floats: omitting them is a malformed request."""
    resp = client.get(AT_POINT, headers=auth_header())
    assert resp.status_code == 422


def test_at_point_requires_auth(client):
    """Same router-level demographics:read guard as the rest: no token -> 401."""
    resp = client.get(CALITRI_POINT)
    assert resp.status_code == 401
