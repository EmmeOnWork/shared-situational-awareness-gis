from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers.demographics.demographics_router import demographics_router
from src.security.auth_dependencies import require_scopes

app = FastAPI(
    title="Demographic Widget Service",
    description="Standalone read-only service serving aggregated ISTAT demographic data.",
    version="0.1.0",
)

# CORS — mirrors the monolith's policy (copied, not imported; see ADR-0001) so the
# same external frontend origins the monolith allows can reach this service too.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok"}


# Demographics routes are guarded at the router level by the demographics:read
# scope, mirroring how the monolith mounts its pollution router.
app.include_router(
    demographics_router,
    dependencies=[Depends(require_scopes(["demographics:read"]))],
)
