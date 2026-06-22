from fastapi import APIRouter

# The Round Manager's data routes. Mounted under ``/rounds`` and guarded as a
# group in src/app.py (authentication-only in v1). This walking-skeleton slice
# carries only a reachability ``ping``; the lobby/roster/vote/WS routes land in
# later slices, each added here behind the same guard.
rounds_router = APIRouter(prefix="/rounds")


@rounds_router.get("/ping")
async def ping():
    """Guarded reachability probe: a 200 here through the gateway proves the
    service is up *and* verifying monolith JWTs (the documented smoke)."""
    return {"status": "ok"}
