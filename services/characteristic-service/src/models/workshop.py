"""API shapes for the Active Workshop frame (the light, no-bytea view).

The characteristic widget is a WRITE widget and deliberately does NOT speak the
read-only ``DataResponse`` contract; it owns these shapes. ``WorkshopView`` is the
light frame returned by ``GET /characteristic/workshops/{poi_id}``: the Scheda
fields plus the Blueprint metadata, never the image bytes.
"""

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, field_validator

# The enum-like Scheda fields are validated HERE, in the app, rather than as DB
# constraints — the columns stay plain ``text``/``text[]`` so the standardised
# (Provincia di Avellino) and legacy (Cassano) field lists map in without DDL
# churn. Centralised so the allowed sets are cheap to refine as the canonical list
# settles. Empty/None always passes: every Scheda field is optional/non-blocking.
TITOLO_VALUES = frozenset({"proprieta", "comodato", "locazione", "altro"})
STATO_USO_VALUES = frozenset({"in_uso", "parziale", "dismesso", "inutilizzato"})
CONDIZIONI_VALUES = frozenset({"buone", "discrete", "scarse", "da_ristrutturare"})
VINCOLI_VALUES = frozenset(
    {"paesaggistico", "culturale", "urbanistico", "nessuno", "altro"}
)


@dataclass(frozen=True)
class BlueprintImage:
    """A Blueprint's raw bytes plus their ``content_type`` — the by-id image
    payload served by ``GET /characteristic/blueprints/{id}``.

    Deliberately NOT a Pydantic API model: this is never JSON, it is the binary
    body itself (the heavy bytea), so it stays out of ``WorkshopView`` and the
    light Sezione listing."""

    image: bytes
    content_type: str


class BlueprintMeta(BaseModel):
    """One Blueprint in the light Sezione listing: its id and Sezione label only.

    The ``image`` bytea is intentionally absent — a Blueprint's bytes are served
    by id on ``GET /characteristic/blueprints/{id}``, so listing a Bene's Sezioni
    never drags the binaries.
    """

    id: int
    sezione: str


class Scheda(BaseModel):
    """The Scheda di Individuazione Immobile for a Bene — the structured reuse
    data, mirroring the ``building_scheda`` columns.

    Every field is optional / non-blocking: the first Load may save a Blueprint
    with the Scheda left empty. Comune/coordinates are NOT here — the POI is the
    source of truth for geographic identity (decision A), shown from the bus, never
    re-stored.
    """

    denominazione: Optional[str] = None
    destinazione_uso: Optional[str] = None
    titolo: Optional[str] = None
    titolo_estremi: Optional[str] = None
    stato_uso: Optional[str] = None
    condizioni: Optional[str] = None
    stato_descrizione: Optional[str] = None
    vincoli: Optional[list[str]] = None
    vincoli_note: Optional[str] = None
    foglio: Optional[str] = None
    particella: Optional[str] = None
    referente_nome: Optional[str] = None
    referente_email: Optional[str] = None
    referente_tel: Optional[str] = None

    # ``titolo`` and ``vincoli`` are intentionally NOT enum-validated: their widget
    # controls let a Master pick "altro" and type a free-text value, saved as-is — a
    # custom ``titolo`` string, or a custom ``vincoli`` member alongside the suggested
    # ones. TITOLO_VALUES / VINCOLI_VALUES are the suggestions the UI offers, not a
    # closed set. ``stato_uso`` / ``condizioni`` (no "altro" option) stay strict.

    @field_validator("stato_uso")
    @classmethod
    def _check_stato_uso(cls, v: Optional[str]) -> Optional[str]:
        return _check_in(v, STATO_USO_VALUES, "stato_uso")

    @field_validator("condizioni")
    @classmethod
    def _check_condizioni(cls, v: Optional[str]) -> Optional[str]:
        return _check_in(v, CONDIZIONI_VALUES, "condizioni")


def _check_in(value: Optional[str], allowed: frozenset[str], field: str) -> Optional[str]:
    """Pass ``None`` (the field is optional) or a value within ``allowed``; reject
    anything else with the allowed set named, so the error is actionable."""
    if value is None or value in allowed:
        return value
    raise ValueError(f"{field} must be one of {sorted(allowed)}; got '{value}'")


class WorkshopView(BaseModel):
    """The Active Workshop frame's data: the Scheda (``null`` until the first Load
    creates it) and the light list of the Bene's Blueprints. The whole shape is
    bytea-free — the heavy image is fetched separately, by id."""

    scheda: Optional[Scheda] = None
    blueprints: list[BlueprintMeta] = []
