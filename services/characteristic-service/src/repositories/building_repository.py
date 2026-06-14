"""Data access for the ``building_*`` tables (the shared ``public`` schema).

A deep module: callers pass a SQLAlchemy session and get domain objects back,
never raw rows or SQL. Slice 2 needs only the read path, ``get_workshop``; the
write paths (``upsert_blueprint``, ``get_blueprint_bytes``, ``upsert_scheda``)
land on this same module in later slices.
"""

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.workshop import BlueprintImage, BlueprintMeta, Scheda, WorkshopView

# Auto-register the Bene's Workshop row on first write. The reuse-service normally
# owns this registry; this is the fallback so a Blueprint can be the first thing
# ever stored for a `poi_id`. ON CONFLICT DO NOTHING makes re-writes a no-op.
_WORKSHOP_REGISTER = text(
    """
    INSERT INTO building_workshop (poi_id) VALUES (:poi_id)
    ON CONFLICT (poi_id) DO NOTHING
    """
)

# Upsert exactly one Blueprint per `(poi_id, sezione)`: a re-upload of the same
# Sezione REPLACES its bytes rather than adding a duplicate (the UNIQUE constraint
# is the seam). RETURNING id surfaces the row's id for the light metadata.
_BLUEPRINT_UPSERT = text(
    """
    INSERT INTO building_blueprint (poi_id, sezione, image, content_type, byte_size)
    VALUES (:poi_id, :sezione, :image, :content_type, :byte_size)
    ON CONFLICT (poi_id, sezione) DO UPDATE
        SET image = EXCLUDED.image,
            content_type = EXCLUDED.content_type,
            byte_size = EXCLUDED.byte_size,
            uploaded_at = now()
    RETURNING id
    """
)

# Fetch a single Blueprint's bytes by id. This is the ONE query that carries the
# `image` bytea — every other read stays light (the Sezione listing never selects
# it), so the heavy binary travels only when an image is actually requested.
_BLUEPRINT_BYTES = text(
    """
    SELECT image, content_type
    FROM building_blueprint
    WHERE id = :id
    """
)

# Delete one Blueprint by id. Touches ONLY ``building_blueprint`` — the Scheda and
# the Workshop row are left intact (the FK cascade runs the other way: dropping a
# Workshop would cascade into its Blueprints, never the reverse). The replace path
# is the upsert above; this is the explicit correction of a mistaken upload.
_BLUEPRINT_DELETE = text(
    """
    DELETE FROM building_blueprint
    WHERE id = :id
    """
)

# The Scheda columns mapped into the API ``Scheda`` — listed by hand (never
# ``SELECT *``) so a future column does not silently widen the payload.
_SCHEDA_QUERY = text(
    """
    SELECT denominazione, destinazione_uso, titolo, titolo_estremi, stato_uso,
           condizioni, stato_descrizione, vincoli, vincoli_note, foglio,
           particella, referente_nome, referente_email, referente_tel
    FROM building_scheda
    WHERE poi_id = :poi_id
    """
)

# Upsert the Scheda for a `poi_id` (1:1 with the Bene). The FIRST Load INSERTs;
# a LATER Load hits the PRIMARY KEY (poi_id) and EDITS the same row via DO UPDATE,
# so create-then-edit never leaves a duplicate. Columns listed by hand (mirrors
# `_SCHEDA_QUERY`) so a future column does not silently widen the write; the
# enum-like and array fields are already validated by the `Scheda` model upstream.
_SCHEDA_UPSERT = text(
    """
    INSERT INTO building_scheda (
        poi_id, denominazione, destinazione_uso, titolo, titolo_estremi,
        stato_uso, condizioni, stato_descrizione, vincoli, vincoli_note,
        foglio, particella, referente_nome, referente_email, referente_tel
    ) VALUES (
        :poi_id, :denominazione, :destinazione_uso, :titolo, :titolo_estremi,
        :stato_uso, :condizioni, :stato_descrizione, :vincoli, :vincoli_note,
        :foglio, :particella, :referente_nome, :referente_email, :referente_tel
    )
    ON CONFLICT (poi_id) DO UPDATE SET
        denominazione = EXCLUDED.denominazione,
        destinazione_uso = EXCLUDED.destinazione_uso,
        titolo = EXCLUDED.titolo,
        titolo_estremi = EXCLUDED.titolo_estremi,
        stato_uso = EXCLUDED.stato_uso,
        condizioni = EXCLUDED.condizioni,
        stato_descrizione = EXCLUDED.stato_descrizione,
        vincoli = EXCLUDED.vincoli,
        vincoli_note = EXCLUDED.vincoli_note,
        foglio = EXCLUDED.foglio,
        particella = EXCLUDED.particella,
        referente_nome = EXCLUDED.referente_nome,
        referente_email = EXCLUDED.referente_email,
        referente_tel = EXCLUDED.referente_tel,
        updated_at = now()
    """
)

# The LIGHT Blueprint listing: id + sezione ONLY. The ``image`` bytea is excluded
# here on purpose — a Sezione list never drags the bytes; the image is served by
# id on ``GET /characteristic/blueprints/{id}``. Ordered by Sezione for a stable
# toggle-list.
_BLUEPRINTS_QUERY = text(
    """
    SELECT id, sezione
    FROM building_blueprint
    WHERE poi_id = :poi_id
    ORDER BY sezione
    """
)


def get_workshop(session: Session, poi_id: int) -> WorkshopView:
    """Return the Active Workshop frame for ``poi_id``: the Scheda (``None`` until
    the first Load creates it) and the light Blueprint listing (id + sezione, no
    bytea).

    A Bene with no Workshop / Scheda / Blueprints reads cleanly as
    ``{scheda: None, blueprints: []}`` — the empty frame, not an error.
    """
    scheda_row = session.execute(_SCHEDA_QUERY, {"poi_id": poi_id}).mappings().first()
    blueprint_rows = (
        session.execute(_BLUEPRINTS_QUERY, {"poi_id": poi_id}).mappings().all()
    )

    return WorkshopView(
        scheda=Scheda(**scheda_row) if scheda_row is not None else None,
        blueprints=[
            BlueprintMeta(id=row["id"], sezione=row["sezione"])
            for row in blueprint_rows
        ],
    )


def upsert_blueprint(
    session: Session,
    poi_id: int,
    sezione: str,
    image: bytes,
    content_type: str,
) -> BlueprintMeta:
    """Store the Blueprint for ``(poi_id, sezione)``, replacing any existing one for
    that Sezione (exactly one per ``(poi_id, sezione)``), and return its light
    ``{id, sezione}`` metadata.

    On the first write for a ``poi_id`` the ``building_workshop`` row is
    auto-registered (the reuse-service normally owns that registry — this is the
    fallback). The bytes are stored as-accepted; server-side downscaling is a later
    slice. The caller commits via this function (one transaction per upload)."""
    session.execute(_WORKSHOP_REGISTER, {"poi_id": poi_id})
    new_id = session.execute(
        _BLUEPRINT_UPSERT,
        {
            "poi_id": poi_id,
            "sezione": sezione,
            "image": image,
            "content_type": content_type,
            "byte_size": len(image),
        },
    ).scalar_one()
    session.commit()
    return BlueprintMeta(id=new_id, sezione=sezione)


def upsert_scheda(session: Session, poi_id: int, scheda: Scheda) -> Scheda:
    """Create-then-edit the Scheda for ``poi_id`` (1:1 with the Bene), folded into
    the Load submission, and return the saved Scheda.

    The first Load INSERTs the row; a later Load EDITS it in place via
    ``ON CONFLICT (poi_id) DO UPDATE`` — never a duplicate. As with a Blueprint
    upload, the first write auto-registers the ``building_workshop`` row (the
    reuse-service normally owns that registry). The enum-like and array fields are
    already validated by the ``Scheda`` model; this layer only persists. The caller
    commits via this function (one transaction per save)."""
    session.execute(_WORKSHOP_REGISTER, {"poi_id": poi_id})
    session.execute(_SCHEDA_UPSERT, {"poi_id": poi_id, **scheda.model_dump()})
    session.commit()
    return scheda


def get_blueprint_bytes(session: Session, blueprint_id: int) -> Optional[BlueprintImage]:
    """Return a single Blueprint's raw bytes + ``content_type`` by id, or ``None``
    if no such Blueprint exists (the router maps that to a 404).

    This is the only read that pulls the ``image`` bytea; the light Sezione listing
    never does, so the heavy binary moves only on an explicit by-id request."""
    row = session.execute(_BLUEPRINT_BYTES, {"id": blueprint_id}).mappings().first()
    if row is None:
        return None
    return BlueprintImage(image=row["image"], content_type=row["content_type"])


def delete_blueprint(session: Session, blueprint_id: int) -> bool:
    """Delete the Blueprint with ``blueprint_id`` and return whether one was removed
    (``False`` for an unknown id — the router maps that to a 404).

    Only ``building_blueprint`` is touched, so a delete leaves the Bene's Scheda and
    Workshop registration intact: it removes a single mistaken Sezione, nothing more.
    The caller commits via this function (one transaction per delete)."""
    result = session.execute(_BLUEPRINT_DELETE, {"id": blueprint_id})
    session.commit()
    return result.rowcount > 0
