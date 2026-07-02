from fastapi import APIRouter, HTTPException, Query, status

from src.routers.likert.competitor_repository import find_competitors
from src.routers.likert.comune_resolver import resolve_comune
from src.routers.likert.gradimento_calculator import RatedPlace, compute_gradimento
from src.routers.likert.ratings_repository import fetch_ratings
from src.routers.likert.vocazione_competitors import get_competitor_category_prefixes

# The Scala Likert's single data route. Mounted under ``/likert`` and guarded as a
# group in src/app.py (authentication-only — not a sensitive widget). The clicked
# point is resolved to a REAL comune, the Active Vocazione to the REAL Competitor
# set in that comune (the SAME set the Concorrenza layer paints), and those
# competitors' cached online ratings are pooled into the REAL Gradimento. The
# payload SHAPE is the contract the widget renders against (PRD "API contract").
likert_router = APIRouter(prefix="/likert")


@likert_router.get("/gradimento")
async def gradimento(
    lat: float = Query(..., description="Latitude of the clicked point"),
    lng: float = Query(..., description="Longitude of the clicked point"),
    vocazione: str = Query(..., description="Active Vocazione slug from the bus"),
):
    """The Gradimento for the Active Vocazione on the clicked comune.

    Resolves ``lat``/``lng`` to the real comune (region, ``area_type_id = 3``), the
    Vocazione to its market Competitors in that comune, and those competitors'
    cached online ratings into the pooled Gradimento. A **civic** Vocazione (empty
    prefix map) has no genuine market competitor ⇒ ``no_competitors`` (the widget
    shows "Nessun concorrente di mercato"); competitors with no cached rating leave
    the answer ``insufficient`` (zero rated ⇒ "dati insufficienti", no needle);
    otherwise ``ok`` with the pooled value, flagged ``low_confidence`` on thin
    coverage. A point in **no** comune (e.g. a sea click) is a 404, rendered as a
    graceful empty state.
    """
    comune = resolve_comune(lat, lng)
    if comune is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No comune contains the point ({lat}, {lng})",
        )

    prefixes = get_competitor_category_prefixes(vocazione)

    # Civic Vocazione: no market competitor by construction — don't even query.
    if not prefixes:
        return _payload(comune, vocazione, "no_competitors", [], {}, None)

    competitors = find_competitors(comune.region_id, prefixes)

    # Pool the cached ratings of the matched + rated competitors into the
    # Gradimento. ``fetch_ratings`` returns only the confidently-matched, rated
    # subset (keyed by poi_id), so a wrong/absent match can never enter the mean.
    ratings = fetch_ratings([c.poi_id for c in competitors])
    grad = compute_gradimento(
        [RatedPlace(rating=r.rating, n_ratings=r.n_ratings) for r in ratings.values()]
    )
    return _payload(comune, vocazione, grad.status, competitors, ratings, grad)


def _payload(comune, vocazione, status, competitors, ratings, grad):
    """Assemble the API-contract payload (PRD). The ``breakdown`` is the matched +
    rated competitors only — each with its ★ and review count — ordered by review
    count desc (so the modal leads with the places that drove the number); an
    unmatched competitor is omitted rather than shown as a misleading 0★. The
    rollup fields come straight from the computed ``grad`` (``None`` only for the
    no-competitor case, where there is nothing to pool)."""
    breakdown = sorted(
        (
            {
                "poi_id": c.poi_id,
                "name": c.name,
                "categoria": c.categoria,
                "rating": ratings[c.poi_id].rating,
                "n_ratings": ratings[c.poi_id].n_ratings,
            }
            for c in competitors
            if c.poi_id in ratings
        ),
        key=lambda row: row["n_ratings"],
        reverse=True,
    )
    # Freshness = the most recent contributing fetch (PRD default), or none yet.
    updated_at = (
        max(r.fetched_at for r in ratings.values()).isoformat() if ratings else None
    )
    return {
        "comune": {"region_id": comune.region_id, "name": comune.name},
        "vocazione": vocazione,
        "status": status,
        "gradimento": grad.value if grad else None,
        "total_reviews": grad.total_reviews if grad else 0,
        "n_competitors": len(competitors),
        "n_rated": grad.n_rated if grad else 0,
        "low_confidence": grad.low_confidence if grad else False,
        "updated_at": updated_at,
        "breakdown": breakdown,
    }
