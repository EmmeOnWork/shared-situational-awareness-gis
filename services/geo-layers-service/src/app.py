from fastapi import Depends, FastAPI

from src.core.security import require_auth
from src.layers.fixed_network.router import router as fixed_network_router
from src.layers.frana.router import router as frana_router
from src.layers.idraulico.router import router as idraulico_router
from src.layers.sismico.router import router as sismico_router

app = FastAPI(
    title="Geo-Layers Service",
    description="External data-source Widget: serves GeoJSON map layers for the monolith's GIS map.",
    version="0.2.0",
)

# One router per layer (src/layers/<name>/router.py), all under the /geo-layers
# prefix already reserved in the gateway Caddyfile.
_LAYER_ROUTERS = (
    fixed_network_router,
    frana_router,
    idraulico_router,
    sismico_router,
)


@app.get("/health")
def health():
    """Liveness probe (unguarded)."""
    return {"status": "ok"}


@app.get("/geo-layers/ping", dependencies=[Depends(require_auth)])
def ping():
    """Auth-and-reachability smoke behind the gateway (no DB)."""
    return {"status": "ok"}


# Data routes are JWT-guarded (auth-only): the browser sends the monolith JWT,
# which the gateway forwards. The bundle/seam needs no scope grant in the monolith.
for _router in _LAYER_ROUTERS:
    app.include_router(_router, dependencies=[Depends(require_auth)])
