"""Unit tests for the pure Prezzario parser + curation (task 03; PRD "Lista B").

Pure-function-in-isolation style (prior art likert ``test_gradimento_calculator.py``):
no TestClient, no DB — feed raw source records, assert the normalized ``VoceRow``
output, the curation include/exclude boundary and the codice→Capitolo association.
The curated Capitolo set is an explicit, re-confirmable editorial list (a new edition
is re-curated, not silently drifted); everything outside it is dropped.
"""

from src.routers.prezzari.prezzario_parser import (
    CURATED_CAPITOLI,
    VoceRow,
    parse_voci,
)


def test_a_curated_renovation_voce_is_parsed_into_a_row():
    """A source record whose codice sits under a curated renovation Capitolo is kept
    and normalized: codice/descrizione/um/prezzo parsed, capitolo derived from the
    codice's leading chapter segment."""
    records = [
        {
            "codice": "E.01.010.a",
            "descrizione": "Demolizione di tramezzatura in muratura",
            "um": "m²",
            "prezzo": "18,40",
        }
    ]

    rows = parse_voci(records)

    assert rows == [
        VoceRow(
            codice="E.01.010.a",
            descrizione="Demolizione di tramezzatura in muratura",
            um="m²",
            prezzo=18.40,
            capitolo="E.01",
        )
    ]


def test_curated_capitoli_is_a_nonempty_explicit_map():
    """The curated set is recorded as an explicit codice→titolo list (not inferred at
    runtime), so a new edition is re-confirmed deliberately."""
    assert CURATED_CAPITOLI
    assert "E.01" in CURATED_CAPITOLI


def test_a_voce_outside_the_curated_capitoli_is_excluded():
    """The curation boundary: a Voce under a non-renovation Capitolo (e.g. roads,
    ``U.05``) is dropped, so the widget never shows roads/aqueducts alongside the
    renovation slice — even in the same source batch as a curated Voce."""
    records = [
        {"codice": "U.05.010.a", "descrizione": "Fresatura di pavimentazione stradale",
         "um": "m²", "prezzo": "3,10"},
        {"codice": "E.01.010.a", "descrizione": "Demolizione di tramezzatura",
         "um": "m²", "prezzo": "18,40"},
    ]

    rows = parse_voci(records)

    assert [row.codice for row in rows] == ["E.01.010.a"]


def test_malformed_and_empty_records_are_skipped():
    """A record missing a required field or carrying an unparseable prezzo is skipped
    rather than crashing the whole ingest — the curated rows around it still land."""
    records = [
        {"codice": "E.01.010.a", "descrizione": "Demolizione", "um": "m²", "prezzo": "18,40"},
        {"codice": "E.01.020.a", "descrizione": "Senza prezzo", "um": "m²", "prezzo": ""},
        {"descrizione": "Senza codice", "um": "m²", "prezzo": "5,00"},
        {},
    ]

    rows = parse_voci(records)

    assert [row.codice for row in rows] == ["E.01.010.a"]
