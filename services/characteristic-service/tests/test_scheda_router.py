from unittest.mock import MagicMock, patch

SCHEDA = "/characteristic/scheda"
WORKSHOPS = "/characteristic/workshops"

# A populated Scheda body as the Load form submits it (JSON). All fields optional;
# the enum-like ones carry allowed values, the rest are free text / arrays.
VALID_BODY = {
    "denominazione": "Ex Macello",
    "destinazione_uso": "Centro civico",
    "titolo": "proprieta",
    "stato_uso": "dismesso",
    "condizioni": "da_ristrutturare",
    "vincoli": ["paesaggistico", "culturale"],
    "referente_email": "tecnico@comune.it",
}


def _patch_upsert_session():
    """Patch the router's session-context so a PUT drives the real ``upsert_scheda``:
    the workshop auto-register executes, then the scheda upsert. Mirrors the
    blueprints-router test pattern."""
    patcher = patch(
        "src.routers.characteristic.characteristic_router.get_session_context"
    )
    mock_get = patcher.start()
    mock_session = MagicMock()
    mock_session.execute.side_effect = [MagicMock(), MagicMock()]
    mock_get.return_value.__enter__.return_value = mock_session
    return patcher, mock_session


def _patch_read_session(scheda_row):
    """Patch the session so a later GET /workshops drives the real ``get_workshop``:
    the scheda lookup (``.first()``) returns the row we just saved, then the light
    blueprint listing (``.all()``) is empty."""
    patcher = patch(
        "src.routers.characteristic.characteristic_router.get_session_context"
    )
    mock_get = patcher.start()
    mock_session = MagicMock()
    scheda_result = MagicMock()
    scheda_result.mappings.return_value.first.return_value = scheda_row
    blueprint_result = MagicMock()
    blueprint_result.mappings.return_value.all.return_value = []
    mock_session.execute.side_effect = [scheda_result, blueprint_result]
    mock_get.return_value.__enter__.return_value = mock_session
    return patcher


def test_save_scheda_then_reads_back_on_the_workshop_frame(client, auth_header):
    """The Scheda write tracer: a valid Scheda saved through the write route (200)
    is then returned, populated, by ``GET /characteristic/workshops/{poi_id}`` — the
    create path of ``upsert_scheda`` folded into the Load submission, read back on the
    Active Workshop frame."""
    patcher, mock_session = _patch_upsert_session()
    try:
        save = client.put(f"{SCHEDA}/7", json=VALID_BODY, headers=auth_header())
    finally:
        patcher.stop()

    assert save.status_code == 200
    mock_session.commit.assert_called_once()

    # The saved Scheda now reads back on the light frame (no bytea), populated.
    patcher = _patch_read_session(VALID_BODY)
    try:
        frame = client.get(f"{WORKSHOPS}/7", headers=auth_header())
    finally:
        patcher.stop()

    assert frame.status_code == 200
    scheda = frame.json()["scheda"]
    assert scheda["denominazione"] == "Ex Macello"
    assert scheda["titolo"] == "proprieta"
    assert scheda["vincoli"] == ["paesaggistico", "culturale"]


def test_save_scheda_requires_auth(client):
    """The Scheda write is WRITE-GUARDED: no JWT -> 401, via the same single
    router-level dependency as the Blueprint upload (the Master-gate seam). No write
    reaches the DB unauthenticated."""
    resp = client.put(f"{SCHEDA}/7", json=VALID_BODY)

    assert resp.status_code == 401


def test_save_scheda_rejects_unknown_enum_value_with_422(client, auth_header):
    """An unknown value in a strict enum-like field is rejected at the route with a
    422 BEFORE any write — the ``Scheda`` body model validates ``stato_uso`` against
    its allowed set, so a bad value never reaches the repository. (``titolo`` is
    deliberately free text and is covered separately.)"""
    bad = {**VALID_BODY, "stato_uso": "abbandonato"}

    resp = client.put(f"{SCHEDA}/7", json=bad, headers=auth_header())

    assert resp.status_code == 422
