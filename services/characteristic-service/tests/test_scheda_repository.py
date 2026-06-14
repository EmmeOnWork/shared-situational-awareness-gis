from unittest.mock import MagicMock

from src.models.workshop import Scheda
from src.repositories.building_repository import upsert_scheda


def _session():
    """A fake session whose two ``execute`` calls answer the workshop auto-register
    then the scheda upsert."""
    session = MagicMock()
    session.execute.side_effect = [MagicMock(), MagicMock()]
    return session


def test_upsert_scheda_auto_registers_workshop_then_upserts_and_commits():
    """The first Load for a ``poi_id`` auto-registers its ``building_workshop`` row
    (the reuse-service normally owns the registry) and then upserts the Scheda — two
    statements, in that order, committed once."""
    session = _session()

    upsert_scheda(session, poi_id=7, scheda=Scheda(denominazione="Ex Macello"))

    assert session.execute.call_count == 2
    first_sql = str(session.execute.call_args_list[0].args[0]).lower()
    second_sql = str(session.execute.call_args_list[1].args[0]).lower()
    assert "building_workshop" in first_sql
    assert "building_scheda" in second_sql
    session.commit.assert_called_once()


def test_upsert_scheda_edits_in_place_on_a_later_load_not_a_duplicate():
    """A later Load EDITS the same row, never inserts a duplicate: the scheda upsert
    is an ``ON CONFLICT (poi_id) DO UPDATE`` (1:1 with the Bene), so create-then-edit
    keeps exactly one Scheda per ``poi_id``."""
    session = _session()

    upsert_scheda(session, poi_id=7, scheda=Scheda(titolo="comodato"))

    scheda_sql = str(session.execute.call_args_list[1].args[0]).lower()
    assert "on conflict" in scheda_sql
    assert "poi_id" in scheda_sql
    assert "do update" in scheda_sql


def test_upsert_scheda_binds_every_field_including_array_vincoli():
    """The full Scheda is persisted — including the array-valued ``vincoli`` — bound
    as parameters (never string-interpolated). The bound params carry the values the
    validated model holds."""
    session = _session()

    upsert_scheda(
        session,
        poi_id=7,
        scheda=Scheda(
            denominazione="Ex Macello",
            titolo="proprieta",
            vincoli=["paesaggistico", "culturale"],
        ),
    )

    params = session.execute.call_args_list[1].args[1]
    assert params["poi_id"] == 7
    assert params["denominazione"] == "Ex Macello"
    assert params["titolo"] == "proprieta"
    assert params["vincoli"] == ["paesaggistico", "culturale"]
