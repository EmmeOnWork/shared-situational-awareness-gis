"""Self-registration into the monolith's shared widget catalog.

The dashboard "Add widget" menu is **DB-driven**: it lists
``dashboards_config.widget_types`` from the shared database (ADR-0001). A Widget
service makes itself appear in that menu by inserting **one** row here — its
catalog entry — so **no monolith code is touched**. The monolith's own boot
upserts only ITS seed rows (``ON CONFLICT (type) DO UPDATE`` over a fixed list),
so this externally-owned row survives every monolith restart untouched.

The catalog row points the generic ``RemoteWidget`` seam at this service's UI
bundle via ``default_props.additionalConfig.remote = {src, tag}`` — the fragment
the frontend's ``makeWidget`` copies into a freshly added widget.

**Best-effort by design.** Registration must never stop the service from booting:
if the catalog table does not exist yet (monolith not booted) or the DB role may
not write the monolith's schema, we log and carry on. An operator can apply
``catalog/widget-type.sql`` instead, or set ``REGISTER_IN_CATALOG=false``.
"""

import json
import logging

from src.config import get_settings
from src.config.pgsql_config import get_session_context, text

logger = logging.getLogger(__name__)

# This service's catalog identity. `type` is the catalog primary key and the
# widget's `type`; it is unique per Widget. The renderer routes by the presence
# of `remote`, not by this string, so the value just needs to be stable + unique.
WIDGET_TYPE = "vocazione"

_CATALOG_ROW = {
    "type": WIDGET_TYPE,
    "label": "Selettore Vocazione",
    "description": "Seleziona la Vocazione attiva (lente del borgo)",
    "category": "data",
    "default_props": {
        "widgetProps": {"title": "Vocazione"},
        "additionalConfig": {
            "remote": {
                "src": "/vocazione/widget.js",
                "tag": "vocazione-widget",
            }
        },
    },
    "sort_order": 20,
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
        sort_order    integer NOT NULL DEFAULT 0
    );
    """
)

# Same upsert shape the monolith uses: refresh only the code-owned `default_props`
# on conflict, leaving operator-owned presentation columns (label/category/…) be.
_UPSERT = text(
    """
    INSERT INTO dashboards_config.widget_types
        (type, label, description, category, default_props, sort_order)
    VALUES
        (:type, :label, :description, :category, CAST(:default_props AS jsonb), :sort_order)
    ON CONFLICT (type) DO UPDATE
        SET default_props = EXCLUDED.default_props
    """
)


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
        logger.info("vocazione widget registered in shared catalog as '%s'", WIDGET_TYPE)
        return True
    except Exception as exc:  # noqa: BLE001 — registration is best-effort
        logger.warning(
            "catalog self-registration skipped (%s); apply catalog/widget-type.sql "
            "manually or set REGISTER_IN_CATALOG=false to silence this",
            exc,
        )
        return False
