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
    """Placeholder endpoint behind the ``demographics:read`` guard.

    Task 03 replaces/extends this with the real read endpoints under the same
    router-level guard.
    """
    return {"status": "ok"}
