from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config.catalog_registration import register_in_catalog
from src.routers.demographics.demographics_router import demographics_router
from src.security.auth_dependencies import require_scopes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Announce this Widget to the shared widget catalog (best-effort, never
    # fatal). Runs on real boot; unit tests use a non-context-managed TestClient,
    # so this does not fire — and never touches a database — during tests.
    register_in_catalog()
    yield


app = FastAPI(
    title="Demographic Widget Service",
    description="Standalone read-only service serving aggregated ISTAT demographic data.",
    version="0.1.0",
    lifespan=lifespan,
)

# The built UI bundle (the Widget's frontend half). Built from ui/ by `make ui`
# locally or the Node stage of the Dockerfile; see
# ../docs/architecture/widget-microservice-fullstack.md.
WIDGET_BUNDLE = Path(__file__).parent / "static" / "demographic-widget.js"


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/demographics/widget.js", include_in_schema=False)
def widget_bundle():
    """Serve the Widget's UI bundle — the frontend half of this full-stack Widget.

    Deliberately **unguarded**: a browser ``<script>`` load carries no bearer
    token, so the *code* is public while the *data* endpoints below stay behind
    the ``demographics:read`` scope. The element receives the host's JWT at
    runtime and uses it for its data calls. Reached through the gateway because
    ``/demographics*`` already routes here — no extra route table entry.
    """
    if not WIDGET_BUNDLE.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "UI bundle not built; run `make ui`."},
        )
    return FileResponse(WIDGET_BUNDLE, media_type="application/javascript")


# Demographics routes are guarded at the router level by the demographics:read
# scope, mirroring how the monolith mounts its pollution router.
app.include_router(
    demographics_router,
    dependencies=[Depends(require_scopes(["demographics:read"]))],
)
