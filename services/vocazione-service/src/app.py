from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config.catalog_registration import register_in_catalog


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On real boot (best-effort, never fatal): announce this Widget to the shared
    # "Add widget" catalog. Unit tests use a non-context-managed TestClient, so
    # this does not fire — and never touches a database — during tests. There is
    # no registry to ensure and no data router to mount: this service owns no
    # tables (ADR-0001).
    register_in_catalog()
    yield


app = FastAPI(
    title="Vocazione Widget Service (Vocazione Selector)",
    description="Serves the <vocazione-widget> bundle and self-registers in the "
    "shared dashboard catalog. Owns no tables and exposes no data route.",
    version="0.1.0",
    lifespan=lifespan,
)

# The built UI bundle (the Widget's frontend half). Built from ui/ by `make ui`
# locally or the Node stage of the Dockerfile.
WIDGET_BUNDLE = Path(__file__).parent / "static" / "vocazione-widget.js"


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/vocazione/widget.js", include_in_schema=False)
def widget_bundle():
    """Serve the Widget's UI bundle — the frontend half of this full-stack Widget.

    Deliberately **unguarded**: a browser ``<script>`` load carries no bearer
    token. Unlike the sibling Widgets there is nothing else to guard — this
    service owns no data route at all; its only output is a browser event. The
    element receives the host's JWT at runtime but, for now, fetches nothing.
    Reached through the gateway because ``/vocazione*`` already routes here — no
    extra route table entry.
    """
    if not WIDGET_BUNDLE.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "UI bundle not built; run `make ui`."},
        )
    # ``no-cache`` = the browser must REVALIDATE before reusing a cached copy, so
    # it can never serve a stale widget after a redeploy (the bug we hit on the
    # sibling Widgets). At a few KB the re-send on revalidation is negligible.
    return FileResponse(
        WIDGET_BUNDLE,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )
