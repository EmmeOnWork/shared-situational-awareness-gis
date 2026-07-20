from fastapi import APIRouter

# The Round Manager's plain-HTTP routes. Mounted under ``/rounds`` and guarded
# as a group in src/app.py (authentication-only). This router carries only a
# reachability ``ping`` — the lobby/roster/vote/recap lifecycle is carried
# entirely over the WebSocket route instead (``rounds_ws_router.py``), guarded
# the same way.
rounds_router = APIRouter(prefix="/rounds")


@rounds_router.get("/ping")
async def ping():
    """Guarded reachability probe: a 200 here through the gateway proves the
    service is up *and* verifying monolith JWTs (the documented smoke)."""
    return {"status": "ok"}
