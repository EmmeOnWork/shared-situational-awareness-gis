from fastapi import APIRouter, HTTPException, Query, status

from src.routers.prezzari.comune_resolver import resolve_comune
from src.routers.prezzari.locazione_repository import (
    current_publication as omi_publication,
)
from src.routers.prezzari.locazione_repository import find_locazione
from src.routers.prezzari.prezzario_repository import (
    current_publication,
    find_voci,
    list_capitoli,
)

# I Prezziari's two data routes. Mounted under ``/prezzari`` and guarded as a group
# in src/app.py (authentication-only — any logged-in user may consult these public
# reference lists; not a sensitive/Bene widget). The left list (Prezziario di
# Locazione, OMI) resolves the clicked point to a real comune and reads its Zone
# OMI rows from the `omi_locazione` snapshot table. The right list (Prezzario dei
# Lavori) reads the curated Campania prezzario from the `prezzario_voci` snapshot
# table, in the PRD "API contract" shape the two-column widget renders against.
prezzari_router = APIRouter(prefix="/prezzari")


@prezzari_router.get("/locazione")
async def locazione(
    lat: float = Query(..., description="Latitude of the clicked point"),
    lng: float = Query(..., description="Longitude of the clicked point"),
):
    """Lista A — the Prezziario di Locazione (OMI rental quotations) for the clicked
    comune: every Zona OMI × tipologia × stato with its min–max canone in
    €/m²/month. Comune-scoped (updates on click).

    The clicked point is resolved to a REAL comune (region, ``area_type_id = 3``); a
    point in **no** comune (a sea click, or a click outside Campania) is a 404, which
    the left column renders as its neutral "Clicca un comune della Campania" prompt. A
    resolved comune with no published OMI answers 200 with an empty ``zone`` (the
    widget's "quotazioni OMI non disponibili" empty state), independent of Lista B."""
    comune = resolve_comune(lat, lng)
    if comune is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No comune contains the point ({lat}, {lng})",
        )
    return {
        "comune": {"region_id": comune.region_id, "name": comune.name},
        "publication": omi_publication(),
        "zone": [
            {
                "zona": z.zona,
                "tipologia": z.tipologia,
                "stato": z.stato,
                "canone_min": z.canone_min,
                "canone_max": z.canone_max,
                "um": z.um,
            }
            for z in find_locazione(comune.region_id)
        ],
    }


@prezzari_router.get("/lavori")
async def lavori(
    capitolo: str | None = Query(None, description="Filter to one Capitolo"),
    q: str | None = Query(None, description="Text search over descriptions"),
):
    """Lista B — the Prezzario dei Lavori: a curated slice of the Regione Campania
    public-works price list (renovation/recovery Capitoli only), navigable by
    Capitolo with a description search. Region-fixed (does NOT change on click): it
    takes no lat/lng and reads the curated snapshot from this service's own table."""
    return {
        "publication": current_publication(),
        "capitoli": [
            {"codice": c.codice, "titolo": c.titolo} for c in list_capitoli()
        ],
        "voci": [
            {
                "codice": v.codice,
                "descrizione": v.descrizione,
                "um": v.um,
                "prezzo": v.prezzo,
                "capitolo": v.capitolo,
            }
            for v in find_voci(capitolo, q)
        ],
    }
