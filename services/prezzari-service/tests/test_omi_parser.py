"""Unit tests for the pure OMI parser + Campania scoping (task 04; PRD "Lista A").

Pure-function-in-isolation style (prior art likert ``test_gradimento_calculator.py``):
no TestClient, no DB — feed raw OMI source records, assert the normalized ``OmiRow``
output and the three independent filters: **locazione only** (compravendita dropped),
**Campania comuni only** (an explicit, re-confirmable province set), and **malformed /
empty rows skipped**. The comune is emitted by its ISTAT code; the region_id mapping is
the ingest's job (needs the DB), not the parser's.
"""

from src.routers.prezzari.omi_parser import (
    CAMPANIA_PROVINCE,
    OmiRow,
    parse_omi,
)


def test_a_locazione_campania_row_is_parsed_into_a_row():
    """An OMI locazione record for a Campania comune is kept and normalized: the
    canone min–max parsed from Italian decimals, the €/m²/month unit attached, the
    comune carried by its ISTAT code for the ingest to map to a region_id."""
    records = [
        {
            "mercato": "locazione",
            "prov": "AV",
            "comune_istat": "064001",
            "zona": "B1",
            "tipologia": "Abitazioni civili",
            "stato": "Normale",
            "canone_min": "3,2",
            "canone_max": "4,5",
        }
    ]

    rows = parse_omi(records)

    assert rows == [
        OmiRow(
            comune_istat="064001",
            zona="B1",
            tipologia="Abitazioni civili",
            stato="Normale",
            canone_min=3.2,
            canone_max=4.5,
            um="€/m²/mese",
        )
    ]


def test_a_compravendita_row_is_dropped():
    """The curation boundary: OMI sale (compravendita) rows are dropped on purpose —
    the reuse pan is market rent — even in the same batch as a locazione row."""
    records = [
        {"mercato": "compravendita", "prov": "NA", "comune_istat": "063049",
         "zona": "B1", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "1500,0", "canone_max": "2200,0"},
        {"mercato": "locazione", "prov": "NA", "comune_istat": "063049",
         "zona": "B1", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "8,0", "canone_max": "12,0"},
    ]

    rows = parse_omi(records)

    assert [r.comune_istat for r in rows] == ["063049"]
    assert rows[0].canone_min == 8.0


def test_a_row_outside_campania_is_dropped():
    """Although the OMI is national, only the Campania provinces are kept: a Roma (RM)
    locazione row is dropped, so the snapshot never carries non-Campania comuni — even
    alongside a Campania row in the same batch."""
    records = [
        {"mercato": "locazione", "prov": "RM", "comune_istat": "058091",
         "zona": "A1", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "10,0", "canone_max": "18,0"},
        {"mercato": "locazione", "prov": "SA", "comune_istat": "065116",
         "zona": "B1", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "5,0", "canone_max": "7,5"},
    ]

    rows = parse_omi(records)

    assert [r.comune_istat for r in rows] == ["065116"]


def test_malformed_and_empty_rows_are_skipped():
    """A locazione Campania record missing a required field (zona) or carrying an
    unparseable/empty canone is skipped rather than crashing the ingest — the valid
    rows around it still land."""
    records = [
        {"mercato": "locazione", "prov": "AV", "comune_istat": "064001",
         "zona": "B1", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "3,2", "canone_max": "4,5"},
        {"mercato": "locazione", "prov": "AV", "comune_istat": "064001",
         "zona": "C2", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "", "canone_max": "4,5"},  # empty canone_min
        {"mercato": "locazione", "prov": "AV", "comune_istat": "064001",
         "zona": "", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "3,0", "canone_max": "4,0"},  # missing zona
        {"mercato": "locazione", "prov": "AV", "comune_istat": "064001",
         "zona": "D3", "tipologia": "Abitazioni civili", "stato": "Normale",
         "canone_min": "n.d.", "canone_max": "4,5"},  # unparseable canone
        {},
    ]

    rows = parse_omi(records)

    assert [r.zona for r in rows] == ["B1"]


def test_campania_province_is_a_nonempty_explicit_set():
    """The Campania province set is recorded explicitly (not inferred at runtime), so
    a new edition is re-confirmed deliberately — Avellino/Benevento/Caserta/Napoli/
    Salerno."""
    assert CAMPANIA_PROVINCE
    assert {"AV", "BN", "CE", "NA", "SA"} <= CAMPANIA_PROVINCE
