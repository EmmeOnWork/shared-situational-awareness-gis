from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config.catalog_registration import register_in_catalog
from src.routers.prezzari.prezzari_router import prezzari_router
from src.security.auth_dependencies import require_scopes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Announce this Widget to the shared "Add widget" catalog (best-effort, never
    # fatal). Runs on real boot; unit tests use a non-context-managed TestClient,
    # so this does not fire — and never touches a database — during tests.
    register_in_catalog()
    yield


app = FastAPI(
    title="I Prezziari Widget Service",
    description="Two reference price lists side by side — the OMI rental "
    "quotations of the clicked comune and a curated slice of the Regione "
    "Campania public-works price list.",
    version="0.1.0",
    lifespan=lifespan,
)


# The built UI bundle (the Widget's frontend half). Built from ui/ by `make ui`
# locally or the Node stage of the Dockerfile, dropped here and baked into the image.
WIDGET_BUNDLE = Path(__file__).parent / "static" / "prezzari-widget.js"


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/prezzari/widget.js", include_in_schema=False)
def widget_bundle():
    """Serve the Widget's UI bundle — the frontend half of this full-stack Widget.

    Deliberately **unguarded**: a browser ``<script>`` load carries no bearer
    token, so the *code* is public while the two data routes stay guarded. The
    element receives the host's JWT at runtime and uses it for its data calls.
    Reached through the gateway because ``/prezzari*`` already routes here.
    """
    if not WIDGET_BUNDLE.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "UI bundle not built; run `make ui`."},
        )
    # ``no-cache`` = the browser must REVALIDATE with the server before reusing a
    # cached copy, so it can never serve a stale widget after a redeploy. Without it
    # browsers cache heuristically and keep serving the OLD bundle even in incognito
    # within a session (a bug the sibling widgets already hit and fixed).
    return FileResponse(
        WIDGET_BUNDLE,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


# Both data routes are guarded as a group: ``require_scopes([])`` requires a valid
# monolith JWT but no particular scope — I Prezziari is authentication-only (any
# logged-in user may consult these public reference lists), not a sensitive (Bene)
# widget. The unguarded bundle route above is the deliberate opposite: a browser
# <script> load carries no token.
app.include_router(
    prezzari_router,
    dependencies=[Depends(require_scopes([]))],
)
