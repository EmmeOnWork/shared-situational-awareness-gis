import io
from unittest.mock import MagicMock, patch

from PIL import Image

BLUEPRINTS = "/characteristic/blueprints"


def _real_image(width: int, height: int, fmt: str) -> bytes:
    """A genuinely decodable raster. From slice 5 the upload path *decodes* every
    image (downscale + finalised cap), so the router tests must send real bytes —
    fake signatures no longer survive the processor."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (255, 255, 255)).save(buf, format=fmt)
    return buf.getvalue()


# A small, in-bounds PNG: passes the processor untouched (within 2400px and the cap).
PNG_BYTES = _real_image(640, 480, "PNG")


def _patch_upsert_session(new_id):
    """Patch the router's session-context so a POST drives the real
    ``upsert_blueprint``: the workshop auto-register executes, then the blueprint
    upsert RETURNs ``new_id``. Mirrors the workshops-router test pattern."""
    patcher = patch(
        "src.routers.characteristic.characteristic_router.get_session_context"
    )
    mock_get = patcher.start()
    mock_session = MagicMock()

    workshop_result = MagicMock()
    blueprint_result = MagicMock()
    blueprint_result.scalar_one.return_value = new_id
    mock_session.execute.side_effect = [workshop_result, blueprint_result]

    mock_get.return_value.__enter__.return_value = mock_session
    return patcher, mock_session


def test_upload_stores_blueprint_and_returns_metadata(client, auth_header):
    """The core write tracer: a valid image + Sezione, with a JWT, stores a
    Blueprint and answers 200 with its light ``{id, sezione}`` metadata — the same
    shape the Sezione then appears as in the toggle-list (state 2 -> state 3)."""
    patcher, mock_session = _patch_upsert_session(new_id=31)
    try:
        resp = client.post(
            BLUEPRINTS,
            data={"poi_id": 7, "sezione": "Piano terra"},
            files={"file": ("plan.png", PNG_BYTES, "image/png")},
            headers=auth_header(),
        )
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.json() == {"id": 31, "sezione": "Piano terra"}
    mock_session.commit.assert_called_once()


def test_upload_requires_auth(client):
    """The upload is WRITE-GUARDED: no JWT -> 401, via the single router-level
    dependency (``require_scopes([])`` today) that later admits the Master gate
    (write scope + per-POI ownership) without touching this route."""
    resp = client.post(
        BLUEPRINTS,
        data={"poi_id": 7, "sezione": "Piano terra"},
        files={"file": ("plan.png", PNG_BYTES, "image/png")},
    )

    assert resp.status_code == 401


def test_upload_rejects_wrong_format_with_clear_error(client, auth_header):
    """A non-image (or unsupported image) upload is rejected up front with a clear
    error and never stored — the format guard runs before any DB write."""
    resp = client.post(
        BLUEPRINTS,
        data={"poi_id": 7, "sezione": "Piano terra"},
        files={"file": ("notes.pdf", b"%PDF-1.4 not an image", "application/pdf")},
        headers=auth_header(),
    )

    assert resp.status_code == 415
    assert "format" in resp.json()["detail"].lower()


def test_upload_accepts_valid_image_with_generic_declared_type(client, auth_header):
    """A browser may send a valid image with a generic/empty declared content_type
    (e.g. ``application/octet-stream`` for a file re-attached via DataTransfer). The
    declared type is unreliable, so a genuinely decodable image is accepted — the
    authoritative format gate is the decode, not the declaration."""
    patcher, _ = _patch_upsert_session(new_id=42)
    try:
        resp = client.post(
            BLUEPRINTS,
            data={"poi_id": 7, "sezione": "Piano terra"},
            files={"file": ("plan.png", PNG_BYTES, "application/octet-stream")},
            headers=auth_header(),
        )
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.json() == {"id": 42, "sezione": "Piano terra"}


def test_upload_rejects_oversized_image_with_clear_error(client, auth_header, monkeypatch):
    """An image past the size cap is rejected with a clear error and not stored.
    The cap is read from Settings, so the test pins a tiny cap rather than building
    a 10 MiB body."""
    from src.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MAX_BLUEPRINT_BYTES", "16")
    try:
        resp = client.post(
            BLUEPRINTS,
            data={"poi_id": 7, "sezione": "Piano terra"},
            files={"file": ("plan.png", PNG_BYTES, "image/png")},
            headers=auth_header(),
        )
    finally:
        get_settings.cache_clear()

    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


def test_upload_accepts_a_valid_jpeg(client, auth_header):
    """The positive side of the format guard: a supported type (JPEG) is accepted
    and stored — proving the validation admits valid uploads, not just rejects."""
    patcher, _session = _patch_upsert_session(new_id=44)
    try:
        resp = client.post(
            BLUEPRINTS,
            data={"poi_id": 7, "sezione": "Prospetto"},
            files={"file": ("front.jpg", _real_image(640, 480, "JPEG"), "image/jpeg")},
            headers=auth_header(),
        )
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.json() == {"id": 44, "sezione": "Prospetto"}


def _patch_bytes_session(row):
    """Patch the router's session-context so ``GET /blueprints/{id}`` drives the
    real ``get_blueprint_bytes`` against a session returning ``row`` (or ``None``)."""
    patcher = patch(
        "src.routers.characteristic.characteristic_router.get_session_context"
    )
    mock_get = patcher.start()
    mock_session = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    mock_session.execute.return_value = result
    mock_get.return_value.__enter__.return_value = mock_session
    return patcher


def test_get_blueprint_serves_bytes_with_content_type(client, auth_header):
    """``GET /characteristic/blueprints/{id}`` returns the stored bytes verbatim
    with the correct ``content_type`` — the lazy, by-id image fetch the Widget makes
    only when a Sezione is selected. This is the only route that carries the bytea."""
    patcher = _patch_bytes_session(
        {"image": b"\x89PNG-stored-bytes", "content_type": "image/png"}
    )
    try:
        resp = client.get(f"{BLUEPRINTS}/31", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == b"\x89PNG-stored-bytes"


def test_get_blueprint_unknown_id_is_404(client, auth_header):
    """An id with no Blueprint is a clean 404, not a 500 — the by-id read returned
    ``None``."""
    patcher = _patch_bytes_session(None)
    try:
        resp = client.get(f"{BLUEPRINTS}/999", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 404


def test_get_blueprint_requires_auth(client):
    """Even the read is behind the router-level auth guard: no JWT -> 401 (any
    logged-in user reads; an anonymous one does not)."""
    resp = client.get(f"{BLUEPRINTS}/31")

    assert resp.status_code == 401


def test_upload_passes_blueprint_through_the_processor(client, auth_header):
    """Acceptance: every stored Blueprint passes through slice-5 processing. An
    oversized real image is downscaled *before* it reaches the repository — the
    bytes handed to ``upsert_blueprint`` are the bounded, processed ones, not the
    raw upload, so storage cannot be polluted by phone-photo-resolution plans."""
    from src.models.workshop import BlueprintMeta

    oversized = _real_image(4800, 1200, "PNG")
    captured = {}

    def fake_upsert(session, poi_id, sezione, image, content_type):
        captured["image"] = image
        captured["content_type"] = content_type
        return BlueprintMeta(id=99, sezione=sezione)

    base = "src.routers.characteristic.characteristic_router"
    with patch(f"{base}.upsert_blueprint", side_effect=fake_upsert), patch(
        f"{base}.get_session_context"
    ):
        resp = client.post(
            BLUEPRINTS,
            data={"poi_id": 7, "sezione": "Piano terra"},
            files={"file": ("plan.png", oversized, "image/png")},
            headers=auth_header(),
        )

    assert resp.status_code == 200
    out = Image.open(io.BytesIO(captured["image"]))
    assert max(out.size) == 2400  # downscaled to the longest-edge cap
    assert len(captured["image"]) < len(oversized)  # processed, not the raw upload
    assert captured["content_type"] == "image/png"


def _patch_delete_session(rowcount):
    """Patch the router's session-context so ``DELETE /blueprints/{id}`` drives the
    real ``delete_blueprint``: the by-id DELETE removes ``rowcount`` rows (1 = the
    Blueprint existed, 0 = unknown id)."""
    patcher = patch(
        "src.routers.characteristic.characteristic_router.get_session_context"
    )
    mock_get = patcher.start()
    mock_session = MagicMock()
    result = MagicMock()
    result.rowcount = rowcount
    mock_session.execute.return_value = result
    mock_get.return_value.__enter__.return_value = mock_session
    return patcher, mock_session


def test_delete_removes_blueprint_and_returns_no_content(client, auth_header):
    """The correction tracer: a Master removes a mistaken Sezione by id, with a JWT,
    and the delete is committed and answers 204 No Content. The Sezione then drops
    out of the toggle-list (and the Widget returns to state 2 if it was the last)."""
    patcher, mock_session = _patch_delete_session(rowcount=1)
    try:
        resp = client.delete(f"{BLUEPRINTS}/31", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 204
    assert resp.content == b""
    mock_session.commit.assert_called_once()


def test_delete_requires_auth(client):
    """The delete is WRITE-GUARDED exactly as the upload is: no JWT -> 401, via the
    same single router-level dependency (``require_scopes([])`` today) that later
    admits the Master gate — no anonymous caller can erase a Blueprint."""
    resp = client.delete(f"{BLUEPRINTS}/31")

    assert resp.status_code == 401


def test_delete_unknown_id_is_404(client, auth_header):
    """An id with no Blueprint is a clean 404, not a silent 204: the repository
    removed nothing (rowcount 0), so the route reports not-found — the same by-id
    signal the GET route gives."""
    patcher, _session = _patch_delete_session(rowcount=0)
    try:
        resp = client.delete(f"{BLUEPRINTS}/999", headers=auth_header())
    finally:
        patcher.stop()

    assert resp.status_code == 404
