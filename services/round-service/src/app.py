from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config.catalog_registration import register_in_catalog
from src.routers.rounds.rounds_router import rounds_router
from src.routers.rounds.rounds_ws_router import rounds_ws_router
from src.security.auth_dependencies import require_scopes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Announce this Widget to the shared "Add widget" catalog (best-effort, never
    # fatal). Runs on real boot; unit tests use a non-context-managed TestClient,
    # so this does not fire — and never touches a database — during tests.
    register_in_catalog()
    yield


app = FastAPI(
    title="Round Manager Widget Service",
    description="Stateful, multi-user, realtime-shared consensus process over a Bene.",
    version="0.1.0",
    lifespan=lifespan,
)

# The built UI bundle (the Widget's frontend half). Built from ui/ by `make ui`
# locally or the Node stage of the Dockerfile.
WIDGET_BUNDLE = Path(__file__).parent / "static" / "round-widget.js"


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/rounds/widget.js", include_in_schema=False)
def widget_bundle():
    """Serve the Widget's UI bundle — the frontend half of this full-stack Widget.

    Deliberately **unguarded**: a browser ``<script>`` load carries no bearer
    token, so the *code* is public while the data/WS routes stay guarded. The
    element receives the host's JWT at runtime and uses it for its data calls.
    Reached through the gateway because ``/rounds*`` already routes here.
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


# The Round Manager's data/WS routes are guarded as a group. v1 is
# authentication-only: `require_scopes([])` requires a valid monolith JWT but no
# particular scope — the seam where a participation scope slots in later without
# touching the routes (a dedicated `rounds:*` scope is out of scope for this PRD).
app.include_router(
    rounds_router,
    dependencies=[Depends(require_scopes([]))],
)

# The per-Bene realtime WebSocket route is mounted UNGUARDED here on purpose: a
# browser cannot put a bearer token on a WS handshake, so the HTTP group guard
# (which reads the Authorization header) would refuse every connection before our
# code runs. The route self-guards instead — it verifies the handshake JWT
# (`?access_token=` / `access_token` subprotocol) with the same key before joining
# the connection to a Bene's room.
app.include_router(rounds_ws_router)
