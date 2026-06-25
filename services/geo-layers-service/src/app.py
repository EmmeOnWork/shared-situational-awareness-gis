from fastapi import Depends, FastAPI

from src.router import geo_layers_router
from src.security import require_auth

app = FastAPI(
    title="Geo-Layers Service",
    description="External data-source Widget: serves GeoJSON map layers for the monolith's GIS map.",
    version="0.1.0",
)


@app.get("/health")
def health():
    """Liveness probe (unguarded)."""
    return {"status": "ok"}


# Data routes are JWT-guarded (auth-only): the browser sends the monolith JWT,
# which the gateway forwards. The bundle/seam needs no scope grant in the monolith.
app.include_router(geo_layers_router, dependencies=[Depends(require_auth)])
