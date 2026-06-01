from unittest.mock import MagicMock, patch

from tests.conftest import make_token

RAW = "/demographics/raw"

# One wide row as the shared public.demographic table stores it (PRD schema).
MILANO_ROW = {
    "territory_name": "Milano",
    "territory_name_istat": "Milano",
    "level": "province",
    "pop_total": 3214.0,
    "pop_italian": 2789.0,
    "pop_foreign": 425.0,
    "age_share_0_14": 12.6,
    "age_share_15_64": 63.9,
    "age_share_65_plus": 23.5,
    "mig_rate_internal": -1.2,
    "mig_rate_foreign": 7.8,
    "mig_rate_total": 6.6,
}


def _patch_session_returning(row):
    """Patch the router's session-context to yield a session whose query
    returns ``row`` (mirrors the pollution router's test pattern)."""
    patcher = patch(
        "src.routers.demographics.demographics_router.get_session_context"
    )
    mock_get_session = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.first.return_value = row
    mock_get_session.return_value.__enter__.return_value = mock_session
    return patcher


def test_get_raw_returns_profile_for_known_territory(client, auth_header):
    patcher = _patch_session_returning(MILANO_ROW)
    try:
        resp = client.get(f"{RAW}?territory=Milano", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    body = resp.json()

    assert body["label"] == "Milano"
    assert body["from_datetime"] is None
    assert body["to_datetime"] is None
    assert body["data"] == {
        "pop_total": 3214.0,
        "pop_italian": 2789.0,
        "pop_foreign": 425.0,
        "age_share_0_14": 12.6,
        "age_share_15_64": 63.9,
        "age_share_65_plus": 23.5,
        "mig_rate_internal": -1.2,
        "mig_rate_foreign": 7.8,
        "mig_rate_total": 6.6,
    }


def test_get_raw_unknown_territory_is_404_not_empty_data(client, auth_header):
    """A name we don't have is an error, not blank data: resolution is the
    Selection layer's job. The DB lookup misses -> 404, never a 200 with an
    empty ``data`` map."""
    patcher = _patch_session_returning(None)
    try:
        resp = client.get(f"{RAW}?territory=Nowhere", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 404


def test_get_raw_missing_territory_param_is_422(client, auth_header):
    """``territory`` is required: omitting it is a malformed request (422), not a
    silent empty answer."""
    resp = client.get(RAW, headers=auth_header())

    assert resp.status_code == 422


def test_get_raw_metadata_carries_honest_reading_context(client, auth_header):
    """The 200 response echoes the Territory + level it actually answered for and
    the column-uniform reading context, so callers can label estimates truthfully.
    Datetimes stay null — demographics are not a time series."""
    patcher = _patch_session_returning(MILANO_ROW)
    try:
        resp = client.get(f"{RAW}?territory=Milano", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    meta = resp.json()["metadata"]

    assert meta["territory_name"] == "Milano"
    assert meta["level"] == "province"
    assert meta["population_unit"] == "thousands"
    assert meta["population_reference_date"] == "2026-01-01"
    assert meta["rates_reference_year"] == 2025
    assert meta["quality_flags"]["pop_total"] == "P"
    assert meta["quality_flags"]["pop_italian"] == "S"

    assert resp.json()["from_datetime"] is None
    assert resp.json()["to_datetime"] is None
