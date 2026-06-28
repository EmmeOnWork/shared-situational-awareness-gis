from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config.catalog_registration import register_in_catalog
from src.config.workshop_registry import ensure_workshop_registry
from src.routers.benes.benes_router import benes_router
from src.security.auth_dependencies import require_scopes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On real boot (best-effort, never fatal): ensure the building_workshop
    # registry we curate exists, then announce this Widget to the shared "Add
    # widget" catalog. Unit tests use a non-context-managed TestClient, so this
    # does not fire — and never touches a database — during tests.
    ensure_workshop_registry()
    register_in_catalog()
    yield


app = FastAPI(
    title="Reuse Widget Service (Workshop Selector)",
    description="Owns the building_workshop registry and serves the Bene toggle-list.",
    version="0.1.0",
    lifespan=lifespan,
)

# The built UI bundle (the Widget's frontend half). Built from ui/ by `make ui`
# locally or the Node stage of the Dockerfile.
WIDGET_BUNDLE = Path(__file__).parent / "static" / "reuse-widget.js"


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/reuse/widget.js", include_in_schema=False)
def widget_bundle():
    """Serve the Widget's UI bundle — the frontend half of this full-stack Widget.

    Deliberately **unguarded**: a browser ``<script>`` load carries no bearer
    token, so the *code* is public while the *data* endpoints below stay behind
    the ``reuse:read`` scope. The element receives the host's JWT at runtime and
    uses it for its data calls. Reached through the gateway because ``/reuse*``
    already routes here — no extra route table entry.
    """
    if not WIDGET_BUNDLE.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "UI bundle not built; run `make ui`."},
        )
    # ``no-cache`` = the browser must REVALIDATE before reusing a cached copy, so it
    # can never serve a stale widget after a redeploy (the bug we hit on the sibling
    # Widgets). At a few KB the re-send on revalidation is negligible.
    return FileResponse(
        WIDGET_BUNDLE,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


# Reuse data routes are guarded at the router level by the reuse:read scope,
# mirroring how the monolith mounts its pollution router.
app.include_router(
    benes_router,
    dependencies=[Depends(require_scopes(["reuse:read"]))],
)
