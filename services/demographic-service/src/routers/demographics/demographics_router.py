from collections.abc import Iterable, Mapping

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from src.config.pgsql_config import get_session_context, text
from src.models.pyd_models import DataResponse

demographics_router = APIRouter(prefix="/demographics", tags=["demographics"])


class Territory(BaseModel):
    """One valid Territory in the discovery list: its official name and level.

    The frontend / Selection layer uses this list to validate selections and
    build a finer-unit -> Territory map across the four scales.
    """

    name: str
    level: str


def build_territory_list(rows: Iterable[Mapping]) -> list[Territory]:
    """Map ``public.demographic`` rows to the discovery list shape.

    Pure: mappings in, ``Territory`` objects out — no HTTP, no DB. Order is
    preserved, so the caller's SQL ``ORDER BY`` defines the result order.
    """
    return [Territory(name=row["territory_name"], level=row["level"]) for row in rows]

# The nine indicators of a Demographic profile, as columns of the wide
# public.demographic row: population by citizenship, age structure, migration.
INDICATOR_COLUMNS = (
    "pop_total",
    "pop_italian",
    "pop_foreign",
    "age_share_0_14",
    "age_share_15_64",
    "age_share_65_plus",
    "mig_rate_internal",
    "mig_rate_foreign",
    "mig_rate_total",
)

# Reading context for the indicators, uniform across every Territory and held in
# metadata (not per row). Sourced from the ISTAT bulletin headers: Table 1
# ("Popolazione residente (migliaia) ... al 1° gennaio 2026") and Table 4
# ("Indicatori del bilancio demografico - Anno 2025").
POPULATION_UNIT = "thousands"
POPULATION_REFERENCE_DATE = "2026-01-01"
RATES_REFERENCE_YEAR = 2025

# Column-uniform ISTAT quality flags, per indicator: (S) = estimated (stima),
# (P) = provisional (provvisorio). From the bulletin headers — Table 1 marks
# Totale population and the migration-balance table (Table 4, "Dati provvisori")
# as provisional, while Italian/foreign population and the age shares are
# estimates. Held in metadata, never per row.
QUALITY_FLAGS = {
    "pop_total": "P",
    "pop_italian": "S",
    "pop_foreign": "S",
    "age_share_0_14": "S",
    "age_share_15_64": "S",
    "age_share_65_plus": "S",
    "mig_rate_internal": "P",
    "mig_rate_foreign": "P",
    "mig_rate_total": "P",
}


def build_demographic_response(row: Mapping) -> DataResponse:
    """Assemble a Demographic profile from one wide ``public.demographic`` row.

    Pure: a mapping in, a ``DataResponse`` out — no HTTP, no DB. ``label`` is the
    Territory name, ``data`` is the nine indicators, and the datetimes are null
    because demographics are not a time series.
    """
    return DataResponse(
        label=row["territory_name"],
        data={column: row[column] for column in INDICATOR_COLUMNS},
        from_datetime=None,
        to_datetime=None,
        metadata={
            "territory_name": row["territory_name"],
            "level": row["level"],
            "population_unit": POPULATION_UNIT,
            "population_reference_date": POPULATION_REFERENCE_DATE,
            "rates_reference_year": RATES_REFERENCE_YEAR,
            "quality_flags": QUALITY_FLAGS,
        },
    )


@demographics_router.get("/raw", response_model=DataResponse)
def get_demographics_raw(
    territory: str = Query(
        ...,
        description="Official Territory name to look up (e.g. 'Milano').",
        examples=["Milano"],
    ),
):
    """Return the Demographic profile for one Territory, by **name**.

    Filtered by name only — no geometry / spatial query (deliberately unlike
    pollution's POINT filter); resolving a finer click to its Territory is the
    Selection layer's job. The lookup uses a **bound** query parameter (no
    string interpolation, no injection surface)."""
    query = text(
        "SELECT * FROM demographic WHERE territory_name = :territory LIMIT 1"
    )
    with get_session_context() as session:
        row = session.execute(query, {"territory": territory}).mappings().first()

    if row is None:
        # A name we don't have is an error, not blank data — resolving a finer
        # click to its Territory is the Selection layer's job, not ours.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No demographic data for territory '{territory}'",
        )

    return build_demographic_response(row)


# Resolve a click (a lat/lng) to the province polygon that CONTAINS it, joining
# the spatial sidecar (public.demographic_boundary) back to the wide demographic
# row by the shared territory_name key. Bound params only (no interpolation); the
# GIST index on geom backs ST_Contains. ST_Point takes (lng, lat) — x then y.
AT_POINT_QUERY = text(
    """
    SELECT d.*
    FROM demographic_boundary b
    JOIN demographic d USING (territory_name)
    WHERE ST_Contains(b.geom, ST_SetSRID(ST_Point(:lng, :lat), 4326))
    LIMIT 1
    """
)

# Has ANY boundary been loaded? Distinguishes "click fell outside every province"
# (fall back to the national row) from "boundaries not seeded yet" (503).
BOUNDARY_EXISTS_QUERY = text("SELECT 1 FROM demographic_boundary LIMIT 1")

# National fallback profile for a click no province contains (e.g. out at sea).
NATIONAL_QUERY = text(
    "SELECT * FROM demographic WHERE level = 'national' LIMIT 1"
)


@demographics_router.get("/at-point", response_model=DataResponse)
def get_demographics_at_point(
    lat: float = Query(..., description="Latitude (WGS84)", examples=[40.9151]),
    lng: float = Query(..., description="Longitude (WGS84)", examples=[15.4344]),
):
    """Resolve a map click to a Territory **by geometry**, and return its profile.

    The host clicks a *comune* the demographic data does not carry; this finds the
    province polygon that contains the point (e.g. a click in Calitri resolves to
    Avellino) and answers with that province's profile. It is the spatial twin of
    ``/raw``: ``/raw`` looks up by name, this one by ``ST_Contains``.

    Falls back to the national row when no province contains the point (a click in
    the sea). Answers ``503`` while ``demographic_boundary`` is empty (boundaries
    not loaded yet — see db/README.md), so the caller can degrade to its manual
    territory picker rather than mistaking it for "no data here"."""
    with get_session_context() as session:
        row = session.execute(
            AT_POINT_QUERY, {"lat": lat, "lng": lng}
        ).mappings().first()
        if row is not None:
            return build_demographic_response(row)

        # No province contained the point. Tell apart an unseeded table (503) from
        # a genuinely-outside click (national fallback, else 404).
        if session.execute(BOUNDARY_EXISTS_QUERY).mappings().first() is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Province boundaries not loaded; run db/load_boundaries.py.",
            )

        national = session.execute(NATIONAL_QUERY).mappings().first()

    if national is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No territory resolved for point ({lat}, {lng})",
        )
    return build_demographic_response(national)


# Discovery list ordered by scale (province -> region -> macro_area ->
# national), then by name within a level. The scale rank lives in the SQL so the
# DB returns rows already ordered; the endpoint carries that order through.
TERRITORIES_QUERY = text(
    """
    SELECT territory_name, level
    FROM demographic
    ORDER BY
        CASE level
            WHEN 'province' THEN 1
            WHEN 'region' THEN 2
            WHEN 'macro_area' THEN 3
            WHEN 'national' THEN 4
            ELSE 5
        END,
        territory_name
    """
)


@demographics_router.get("/territories", response_model=list[Territory])
def list_territories():
    """List every valid Territory as ``{name, level}``, ordered by scale then name.

    A discovery endpoint for the frontend / Selection layer to validate
    selections and move between scales. Like the rest of the router it is name-
    based and performs no geometry / spatial query."""
    with get_session_context() as session:
        rows = session.execute(TERRITORIES_QUERY).mappings().all()

    return build_territory_list(rows)


@demographics_router.get("/ping")
def ping():
    """Auth-and-reachability probe behind the ``demographics:read`` guard.

    The only DB-free endpoint inside the guarded router, kept deliberately: the
    auth test suite targets it (``PROTECTED = "/demographics/ping"``) and it is
    the documented gateway reachability smoke — a ``demographics:read`` token
    returns 200 through the gateway *without* seeding the database. The real read
    endpoints (``/raw``, ``/at-point``, ``/territories``) all hit the DB, so they
    cannot stand in for that check.
    """
    return {"status": "ok"}
