from unittest.mock import MagicMock

from src.repositories.building_repository import (
    delete_blueprint,
    get_blueprint_bytes,
    upsert_blueprint,
)


def _upsert_session(returned_id):
    """A fake session whose two ``execute`` calls answer the workshop auto-register
    then the blueprint upsert (``.scalar_one()`` -> the row id)."""
    session = MagicMock()
    workshop_result = MagicMock()
    blueprint_result = MagicMock()
    blueprint_result.scalar_one.return_value = returned_id
    session.execute.side_effect = [workshop_result, blueprint_result]
    return session


def test_upsert_blueprint_auto_registers_workshop_then_returns_metadata():
    """First write for a ``poi_id`` auto-registers its ``building_workshop`` row
    (the reuse-service normally owns the registry) and the blueprint upsert returns
    the light ``{id, sezione}`` metadata. Two statements, in that order, committed."""
    session = _upsert_session(returned_id=31)

    meta = upsert_blueprint(
        session, poi_id=7, sezione="Piano terra", image=b"\x89PNG...", content_type="image/png"
    )

    assert (meta.id, meta.sezione) == (31, "Piano terra")
    # Workshop auto-register first, then the blueprint upsert — both, in order.
    assert session.execute.call_count == 2
    first_sql = str(session.execute.call_args_list[0].args[0]).lower()
    second_sql = str(session.execute.call_args_list[1].args[0]).lower()
    assert "building_workshop" in first_sql
    assert "building_blueprint" in second_sql
    session.commit.assert_called_once()


def test_upsert_blueprint_replaces_on_sezione_collision():
    """Re-uploading the same Sezione is a REPLACE, not a duplicate: the blueprint
    upsert is an ``ON CONFLICT (poi_id, sezione) DO UPDATE`` so there stays exactly
    one Blueprint per ``(poi_id, sezione)``."""
    session = _upsert_session(returned_id=31)

    upsert_blueprint(
        session, poi_id=7, sezione="Piano terra", image=b"new-bytes", content_type="image/png"
    )

    blueprint_sql = str(session.execute.call_args_list[1].args[0]).lower()
    assert "on conflict" in blueprint_sql
    assert "sezione" in blueprint_sql
    assert "do update" in blueprint_sql


def _bytes_session(row):
    """A fake session whose single ``execute`` answers the by-id image lookup
    (``.first()`` -> the image row, or ``None`` when absent)."""
    session = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = row
    session.execute.return_value = result
    return session


def test_get_blueprint_bytes_round_trips_image_and_content_type():
    """The by-id read round-trips exactly what was stored: the raw bytes plus their
    ``content_type`` — so ``GET /characteristic/blueprints/{id}`` can serve the
    image verbatim."""
    session = _bytes_session({"image": b"\x89PNG-stored", "content_type": "image/png"})

    image = get_blueprint_bytes(session, 31)

    assert image is not None
    assert image.image == b"\x89PNG-stored"
    assert image.content_type == "image/png"


def test_get_blueprint_bytes_returns_none_for_unknown_id():
    """An id with no Blueprint reads as ``None`` (the router turns that into a 404),
    never an error."""
    session = _bytes_session(None)

    assert get_blueprint_bytes(session, 999) is None


def _delete_session(rowcount):
    """A fake session whose single ``execute`` answers the by-id delete; ``rowcount``
    is how many rows the DELETE removed (1 = a Blueprint existed, 0 = unknown id)."""
    session = MagicMock()
    result = MagicMock()
    result.rowcount = rowcount
    session.execute.return_value = result
    return session


def test_delete_blueprint_removes_row_and_commits():
    """Delete-by-id removes the Blueprint: a single DELETE on ``building_blueprint``
    keyed by id, committed, reporting ``True`` because a row was removed. This is the
    correction path — a Master un-doing a mistaken upload."""
    session = _delete_session(rowcount=1)

    deleted = delete_blueprint(session, 31)

    assert deleted is True
    sql = str(session.execute.call_args.args[0]).lower()
    assert "delete" in sql
    assert "building_blueprint" in sql
    session.commit.assert_called_once()


def test_delete_blueprint_returns_false_for_unknown_id():
    """An id with no Blueprint removes nothing (rowcount 0) and reports ``False`` —
    the router turns that into a 404, never an error."""
    session = _delete_session(rowcount=0)

    assert delete_blueprint(session, 999) is False


def test_delete_blueprint_leaves_scheda_untouched():
    """A Blueprint delete is a single-table DELETE on ``building_blueprint`` — it
    never reaches ``building_scheda`` or ``building_workshop``, so the Bene's Scheda
    and its registry row survive a Sezione being removed (AC: Scheda intact)."""
    session = _delete_session(rowcount=1)

    delete_blueprint(session, 31)

    assert session.execute.call_count == 1
    sql = str(session.execute.call_args.args[0]).lower()
    assert "building_scheda" not in sql
    assert "building_workshop" not in sql
