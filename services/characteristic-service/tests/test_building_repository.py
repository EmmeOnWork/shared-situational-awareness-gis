from unittest.mock import MagicMock

from src.repositories.building_repository import get_workshop


def _session(scheda_row, blueprint_rows):
    """A fake session whose two ``execute`` calls answer the scheda lookup
    (``.first()``) then the light blueprint listing (``.all()``)."""
    session = MagicMock()
    scheda_result = MagicMock()
    scheda_result.mappings.return_value.first.return_value = scheda_row
    blueprint_result = MagicMock()
    blueprint_result.mappings.return_value.all.return_value = blueprint_rows
    session.execute.side_effect = [scheda_result, blueprint_result]
    return session


def test_get_workshop_returns_blueprint_metadata_without_bytes():
    """The light listing: each Blueprint as ``{id, sezione}`` only. The image
    bytea is deliberately absent — it is served by id, never carried in the list."""
    session = _session(
        scheda_row=None,
        blueprint_rows=[
            {"id": 31, "sezione": "Piano terra"},
            {"id": 32, "sezione": "Sezione A-A"},
        ],
    )

    view = get_workshop(session, 7)

    assert [(b.id, b.sezione) for b in view.blueprints] == [
        (31, "Piano terra"),
        (32, "Sezione A-A"),
    ]
    # The metadata model has no image/bytea field at all.
    assert not hasattr(view.blueprints[0], "image")


def test_get_workshop_maps_scheda_fields_when_a_row_exists():
    """When a Scheda row exists, its fields surface on the view — including the
    array-valued ``vincoli``. (No bytea is involved: the Scheda is structured
    fields, not a binary.)"""
    session = _session(
        scheda_row={
            "denominazione": "Ex Macello",
            "destinazione_uso": "Centro civico",
            "titolo": "proprieta",
            "vincoli": ["paesaggistico", "culturale"],
            "referente_email": "tecnico@comune.it",
        },
        blueprint_rows=[],
    )

    view = get_workshop(session, 7)

    assert view.scheda is not None
    assert view.scheda.denominazione == "Ex Macello"
    assert view.scheda.destinazione_uso == "Centro civico"
    assert view.scheda.titolo == "proprieta"
    assert view.scheda.vincoli == ["paesaggistico", "culturale"]
    assert view.scheda.referente_email == "tecnico@comune.it"


def test_get_workshop_empty_bene_reads_as_null_scheda_and_no_blueprints():
    """A Bene with no Scheda and no Blueprints is the empty frame:
    ``{scheda: None, blueprints: []}`` — not an error. This is State 2 (Active
    Workshop, 0 Blueprints) for the UI."""
    session = _session(scheda_row=None, blueprint_rows=[])

    view = get_workshop(session, 999)

    assert view.scheda is None
    assert view.blueprints == []
