from unittest.mock import MagicMock, patch

WORKSHOPS = "/characteristic/workshops"

# Blueprint rows as the light query returns them: id + sezione ONLY, never the
# `image` bytea (that is served by id on a separate route). poi 7 has one Sezione.
BLUEPRINT_ROWS = [{"id": 31, "sezione": "Piano terra"}]


def _patch_session(scheda_row, blueprint_rows):
    """Patch the router's session-context so ``get_workshop`` sees a session whose
    two queries return ``scheda_row`` (``.first()``) then ``blueprint_rows``
    (``.all()``) — mirrors the demographic / reuse router test pattern."""
    patcher = patch(
        "src.routers.characteristic.characteristic_router.get_session_context"
    )
    mock_get = patcher.start()
    mock_session = MagicMock()

    scheda_result = MagicMock()
    scheda_result.mappings.return_value.first.return_value = scheda_row
    blueprint_result = MagicMock()
    blueprint_result.mappings.return_value.all.return_value = blueprint_rows
    mock_session.execute.side_effect = [scheda_result, blueprint_result]

    mock_get.return_value.__enter__.return_value = mock_session
    return patcher


def test_get_workshop_returns_light_shape_without_bytea(client, auth_header):
    """The Active Workshop frame: ``{scheda, blueprints:[{id,sezione}]}`` — the
    LIGHT shape. A valid JWT gets 200 (auth-only guard), the Sezione list carries
    id + sezione, and the image bytes never appear in the listing payload."""
    patcher = _patch_session(scheda_row=None, blueprint_rows=BLUEPRINT_ROWS)
    try:
        resp = client.get(f"{WORKSHOPS}/7", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"scheda": None, "blueprints": [{"id": 31, "sezione": "Piano terra"}]}
    # No bytea leaks into the light listing — defends the by-id blueprint seam.
    assert "image" not in body["blueprints"][0]


def test_get_workshop_requires_auth(client):
    """The frame inherits the router-level auth-only guard: no token -> 401, never
    an unguarded read of a Bene's Scheda/Blueprint listing."""
    resp = client.get(f"{WORKSHOPS}/7")

    assert resp.status_code == 401
