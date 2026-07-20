from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config.catalog_registration import register_in_catalog
from src.routers.characteristic.characteristic_router import characteristic_router
from src.security.auth_dependencies import require_scopes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Announce this Widget to the shared widget catalog (best-effort, never
    # fatal). Runs on real boot; unit tests use a non-context-managed TestClient,
    # so this does not fire — and never touches a database — during tests.
    register_in_catalog()
    yield


app = FastAPI(
    title="Characteristic Widget Service",
    description="Standalone write service for Building Characteristics (Scheda + Blueprints).",
    version="0.1.0",
    lifespan=lifespan,
)

# The built UI bundle (the Widget's frontend half). Built from ui/ by `make ui`
# locally or the Node stage of the Dockerfile.
WIDGET_BUNDLE = Path(__file__).parent / "static" / "characteristic-widget.js"


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/characteristic/widget.js", include_in_schema=False)
def widget_bundle():
    """Serve the Widget's UI bundle — the frontend half of this full-stack Widget.

    Deliberately **unguarded**: a browser ``<script>`` load carries no bearer
    token, so the *code* is public while the write/data endpoints stay behind the
    auth guard. The element receives the host's JWT at runtime and uses it for its
    data calls. Reached through the gateway because ``/characteristic*`` already
    routes here — no extra route table entry.
    """
    if not WIDGET_BUNDLE.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "UI bundle not built; run `make ui`."},
        )
    # ``no-cache`` = the browser must REVALIDATE with the server before reusing a
    # cached copy, so it can never serve a stale widget after a redeploy. Without it
    # the bundle carries no freshness directive, so browsers cache it heuristically
    # and keep serving the OLD widget — even in incognito within a session (the bug
    # we hit). A bare FileResponse doesn't emit 304s, so revalidation re-sends the
    # full bundle; at ~26 KB that's negligible and worth the guaranteed freshness.
    return FileResponse(
        WIDGET_BUNDLE,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


# The characteristic routes are guarded by a single router-level dependency. v1 is
# authentication-only: `require_scopes([])` requires a valid JWT but no particular
# scope. This is the one seam where the Workshop Master gate (a write scope +
# per-POI ownership) slots in later without touching the routes themselves.
app.include_router(
    characteristic_router,
    dependencies=[Depends(require_scopes([]))],
)
