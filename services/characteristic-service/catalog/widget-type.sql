-- Manual catalog registration for the characteristic Widget.
--
-- The service self-registers on boot (src/config/catalog_registration.py). Use
-- this SQL instead when REGISTER_IN_CATALOG=false, or when the service's DB role
-- may not write the monolith's `dashboards_config` schema and an operator with
-- rights applies it once. It is the same upsert, kept in sync with that module.
--
-- Effect: the characteristic Widget becomes available in the DB-driven widget
-- catalog (dashboards_config.widget_types), so a dashboard curated in Postgres
-- can reference it (there is no in-app "Add widget" menu — dashboards are
-- hand-curated JSON, filtered per stakeholder role via allowed_roles). The
-- `remote` pointer routes the monolith's generic RemoteWidget seam at this
-- service's UI bundle (/characteristic/widget.js → <characteristic-widget>). No
-- monolith code is involved — registration is data.

INSERT INTO dashboards_config.widget_types
    (type, label, description, category, default_props, sort_order)
VALUES (
    'characteristic',
    'Caratteristiche edificio',
    'Schede di riuso e planimetrie del Bene',
    'data',
    '{
        "widgetProps": {"title": "Caratteristiche edificio"},
        "additionalConfig": {
            "remote": {"src": "/characteristic/widget.js", "tag": "characteristic-widget"}
        }
    }'::jsonb,
    90
)
ON CONFLICT (type) DO UPDATE
    SET default_props = EXCLUDED.default_props;
