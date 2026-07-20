from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from src.config.catalog_registration import register_in_catalog
from src.routers.notifications.notifications_router import notifications_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On real boot (best-effort, never fatal): announce this Widget to the shared
    # catalog flagged as an overlay (ADR-0006). Unit tests use a
    # non-context-managed TestClient, so this does not fire — and never touches a
    # database — during tests. There is no data router and no registry to mount:
    # this service owns no tables (ADR-0001).
    register_in_catalog()
    yield


app = FastAPI(
    title="Realtime Notifier Service",
    description="Serves the <notification-overlay> bundle and self-registers in "
    "the shared dashboard catalog as a page-global overlay. Owns no tables.",
    version="0.1.0",
    lifespan=lifespan,
)

# The built UI bundle (the Widget's frontend half). Built from ui/ by `make ui`
# locally or the Node stage of the Dockerfile.
WIDGET_BUNDLE = Path(__file__).parent / "static" / "notification-overlay.js"


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/notifications/widget.js", include_in_schema=False)
def widget_bundle():
    """Serve the Widget's UI bundle — the frontend half of this full-stack Widget.

    Deliberately **unguarded**: a browser ``<script>`` load carries no bearer
    token. The Notifier owns no data route to guard; its only HTTP output beyond
    /health is this bundle (the authenticated WebSocket is a later slice). The
    overlay element receives the host's JWT at runtime via its ``token``
    attribute. Reached through the gateway because ``/notifications*`` already
    routes here — no extra route table entry.
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


# The realtime surfaces: the WS endpoint clients subscribe to and the publish
# ingress that fans a Notification to all of them. The WS handshake verifies the
# monolith JWT (src/notifier/ws_auth.py); authorisation on the publish ingress
# remains a separate, deferred decision (CONTEXT.md).
app.include_router(notifications_router)
