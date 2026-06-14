from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from src.config import get_settings
from src.config.pgsql_config import get_session_context
from src.imaging.blueprint_processor import (
    SUPPORTED_CONTENT_TYPES,
    UnsupportedImageFormat,
    process_blueprint,
)
from src.models.workshop import BlueprintMeta, Scheda, WorkshopView
from src.repositories.building_repository import (
    delete_blueprint,
    get_blueprint_bytes,
    get_workshop,
    upsert_blueprint,
    upsert_scheda,
)

characteristic_router = APIRouter(prefix="/characteristic", tags=["characteristic"])


@characteristic_router.get("/workshops/{poi_id}", response_model=WorkshopView)
def get_workshop_frame(poi_id: int):
    """Return the Active Workshop frame for a Bene: the light, bytea-free
    ``{scheda, blueprints:[{id, sezione}]}``.

    The Scheda is ``null`` until the first Load creates it and the Blueprint list
    may be empty — both are valid empty/idle frames, not errors, so this answers
    200 for any Bene. Guarded by the router-level auth-only dependency (any valid
    JWT reads). The image bytes are never here; they are served by id on a separate
    route. ``response_model`` pins the wire shape so nothing wider can leak out.
    """
    with get_session_context() as session:
        return get_workshop(session, poi_id)


@characteristic_router.put("/scheda/{poi_id}", response_model=Scheda)
def save_scheda(poi_id: int, scheda: Scheda):
    """Create-then-edit the Scheda for a Bene (1:1 with ``poi_id``), folded into the
    Load submission, and return the saved Scheda.

    **Write-guarded** by the same router-level dependency as the Blueprint upload —
    the single Master-gate seam (v1 authentication-only). The body is the ``Scheda``
    model, so its enum-like fields (``titolo``/``stato_uso``/``condizioni``) and the
    multi-valued ``vincoli`` are validated up front: an unknown value is a 422 before
    any write. Every field is optional, so an empty body is a valid (empty) Scheda —
    a Blueprint may still be saved with the Scheda left empty. The first save
    auto-registers the Bene's Workshop row."""
    with get_session_context() as session:
        return upsert_scheda(session, poi_id=poi_id, scheda=scheda)


@characteristic_router.post("/blueprints", response_model=BlueprintMeta)
async def upload_blueprint(
    poi_id: int = Form(...),
    sezione: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload (create or replace) the Blueprint for a ``(poi_id, sezione)`` and
    return its light ``{id, sezione}`` metadata, which the toggle-list renders.

    **Write-guarded** by the router-level dependency — the single Master-gate seam
    (v1 authentication-only). The upload is guarded in two stages: a cheap
    pre-decode reject (a wrong *declared* format is 415, an over-the-input-cap body
    is 413), then the slice-5 image-processor decodes, downscales and size-caps the
    bytes — so every stored Blueprint is bounded and legible. The first write for a
    ``poi_id`` auto-registers its Workshop row."""
    image = await file.read()
    _validate_blueprint(file.content_type, len(image))
    try:
        processed = process_blueprint(image, file.content_type)
    except UnsupportedImageFormat as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc

    with get_session_context() as session:
        return upsert_blueprint(
            session,
            poi_id=poi_id,
            sezione=sezione,
            image=processed.image,
            content_type=processed.content_type,
        )


@characteristic_router.get("/blueprints/{blueprint_id}")
def get_blueprint(blueprint_id: int):
    """Serve a single Blueprint's image bytes with its stored ``content_type``.

    This is the ONLY route that carries the ``bytea`` — the Widget fetches it
    **lazily**, only when a Sezione is selected, so the light listing never drags
    every plan upfront. Authentication-only (the router guard): any logged-in user
    reads. An unknown id is a clean 404, not a 500."""
    with get_session_context() as session:
        image = get_blueprint_bytes(session, blueprint_id)
    if image is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found")
    return Response(content=image.image, media_type=image.content_type)


@characteristic_router.delete("/blueprints/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_blueprint(blueprint_id: int):
    """Remove a single Blueprint by id so a Master can correct a mistaken upload.

    **Write-guarded** by the same router-level dependency as the upload — the single
    Master-gate seam (v1 authentication-only). Only the Blueprint is removed; the
    Bene's Scheda and Workshop registration are untouched. A successful delete is
    204 No Content; an unknown id is a clean 404, not a silent 204 — the same by-id
    'not found' signal the GET route gives, so a stale toggle-list click is told."""
    with get_session_context() as session:
        deleted = delete_blueprint(session, blueprint_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found")


# Declared content_types we do NOT fast-reject: empty/None plus the generic binary
# placeholders a browser may send for a perfectly valid image (e.g. a file that was
# re-attached via DataTransfer, or one the OS didn't map to an image MIME). For these
# the declared type is unreliable, so the authoritative Pillow decode decides.
_DEFER_CONTENT_TYPES = frozenset({"application/octet-stream", "binary/octet-stream"})


def _validate_blueprint(content_type: str | None, byte_size: int) -> None:
    """Cheap pre-decode guard: reject a Blueprint upload whose body is past the input
    cap (413), and FAST-fail only a *clearly* non-image declared type (e.g.
    ``application/pdf``) with a 415 — before the bytes are decoded. A declared
    ``image/*`` type, or a generic/empty one, is unreliable, so the real format gate
    is the decode-based check in the image-processor (which 415s a non-image all the
    same). A valid upload returns silently."""
    declared = (content_type or "").strip().lower()
    if declared and not declared.startswith("image/") and declared not in _DEFER_CONTENT_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_CONTENT_TYPES))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported image format '{content_type}'. Allowed: {allowed}.",
        )
    max_bytes = get_settings().max_blueprint_bytes
    if byte_size > max_bytes:
        raise HTTPException(
            status_code=413,  # Content Too Large
            detail=f"Image too large ({byte_size} bytes); the cap is {max_bytes} bytes.",
        )


@characteristic_router.get("/ping")
def ping():
    """Auth-and-reachability probe behind the v1 write-guard.

    The router carries a single guard dependency — ``require_scopes([])``,
    authentication-only — so any valid JWT returns 200 here and a missing/invalid
    token returns 401. That empty-scope guard is the seam where the Workshop
    Master gate slots in later. The auth suite targets this endpoint
    (``PROTECTED = "/characteristic/ping"``) and it is the documented gateway
    reachability smoke: a valid token returns 200 through the gateway **without**
    touching the database, which the DB-backed write routes cannot stand in for.
    """
    return {"status": "ok"}
