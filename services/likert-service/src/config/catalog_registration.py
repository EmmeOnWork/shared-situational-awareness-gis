"""Self-registration into the monolith's shared widget catalog.

The widget catalog is **DB-driven**: it is
``dashboards_config.widget_types`` from the shared database (ADR-0001), the
source hand-curated dashboards reference (there is no in-app "Add widget"
menu). A Widget service makes itself available to a curated dashboard by
inserting **one** row here — its catalog entry — so **no monolith code is
touched**. The monolith's own boot
upserts only ITS seed rows (``ON CONFLICT (type) DO UPDATE`` over a fixed list),
so this externally-owned row survives every monolith restart untouched.

The catalog row points the generic ``RemoteWidget`` seam at this service's UI
bundle via ``default_props.additionalConfig.remote = {src, tag}`` — the same
fragment shape a dashboard's hand-curated ``additionalConfig`` carries for this
widget type.

**Best-effort by design.** Registration must never stop the service from serving
data: if the catalog table does not exist yet (monolith not booted) or the DB
role may not write the monolith's schema, we log and carry on. An operator can
apply ``catalog/widget-type.sql`` instead, or set ``REGISTER_IN_CATALOG=false``.
"""

import json
import logging

from sqlalchemy import ARRAY, String, bindparam

from src.config import get_settings
from src.config.pgsql_config import get_session_context, text

logger = logging.getLogger(__name__)

# This service's catalog identity. `type` is the catalog primary key and the
# widget's `type`; it is unique per Widget. The renderer routes by the presence
# of `remote`, not by this string, so the value just needs to be stable + unique.
WIDGET_TYPE = "likert"

_CATALOG_ROW = {
    "type": WIDGET_TYPE,
    "label": "Scala Likert",
    "description": "Gradimento locale della Vocazione attiva sul comune cliccato",
    "category": "data",
    "default_props": {
        "widgetProps": {"title": "Scala Likert"},
        "additionalConfig": {
            "remote": {
                "src": "/likert/widget.js",
                "tag": "likert-widget",
            }
        },
    },
    "sort_order": 96,
    # Role-based visibility (stakeholder_role): the Gradimento is relevant to the
    # institutional and economic stakeholders, not the technical one.
    "allowed_roles": ["istituzionale", "economico"],
}

# Ensure the catalog table exists before inserting, so registration does NOT
# depend on the monolith having booted first (the tiny Widget service usually
# wins the boot race). This is the exact shape of the monolith's table — a
# minimal, deliberate coupling to the one table we register into — and IF NOT
# EXISTS makes it a harmless no-op when the monolith already created it.
_ENSURE_CATALOG = text(
    """
    CREATE SCHEMA IF NOT EXISTS dashboards_config;
    CREATE TABLE IF NOT EXISTS dashboards_config.widget_types (
        type          text PRIMARY KEY,
        label         text NOT NULL,
        description   text,
        category      text,
        default_props jsonb NOT NULL DEFAULT '{}'::jsonb,
        enabled       boolean NOT NULL DEFAULT true,
        sort_order    integer NOT NULL DEFAULT 0,
        allowed_roles text[]
    );
    ALTER TABLE dashboards_config.widget_types
        ADD COLUMN IF NOT EXISTS allowed_roles text[];
    """
)

# Same upsert shape the monolith uses: on conflict refresh only the code-owned
# columns — `default_props` and this Widget's role policy `allowed_roles` — leaving
# operator-owned presentation columns (label/category/…) be. `allowed_roles` is bound
# as a text[] so the Python list maps to the Postgres array column.
_UPSERT = text(
    """
    INSERT INTO dashboards_config.widget_types
        (type, label, description, category, default_props, sort_order, allowed_roles)
    VALUES
        (:type, :label, :description, :category, CAST(:default_props AS jsonb),
         :sort_order, :allowed_roles)
    ON CONFLICT (type) DO UPDATE
        SET default_props = EXCLUDED.default_props,
            allowed_roles = EXCLUDED.allowed_roles
    """
).bindparams(bindparam("allowed_roles", type_=ARRAY(String)))


def register_in_catalog() -> bool:
    """Best-effort upsert of this Widget's catalog row. Never raises.

    Returns True on success, False if registration was skipped or failed (which
    is logged) — the service stays fully functional either way.
    """
    if not get_settings().register_in_catalog:
        logger.info("catalog self-registration disabled (REGISTER_IN_CATALOG=false)")
        return False

    params = {**_CATALOG_ROW, "default_props": json.dumps(_CATALOG_ROW["default_props"])}
    try:
        with get_session_context() as session:
            session.execute(_ENSURE_CATALOG)
            session.execute(_UPSERT, params)
            session.commit()
        logger.info("Scala Likert widget registered in shared catalog as '%s'", WIDGET_TYPE)
        return True
    except Exception as exc:  # noqa: BLE001 — registration is best-effort
        logger.warning(
            "catalog self-registration skipped (%s); apply catalog/widget-type.sql "
            "manually or set REGISTER_IN_CATALOG=false to silence this",
            exc,
        )
        return False
