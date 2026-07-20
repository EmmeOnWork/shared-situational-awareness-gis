-- Manual catalog registration for the Round Manager Widget.
--
-- The service self-registers on boot (src/config/catalog_registration.py). Use
-- this SQL instead when REGISTER_IN_CATALOG=false, or when the service's DB role
-- may not write the monolith's `dashboards_config` schema and an operator with
-- rights applies it once. It is the same upsert, kept in sync with that module.
--
-- Effect: the Round Manager Widget becomes available in the DB-driven widget
-- catalog (dashboards_config.widget_types), so a dashboard curated in Postgres
-- can reference it (there is no in-app "Add widget" menu). The `remote` pointer
-- routes the monolith's generic RemoteWidget seam at this service's UI bundle
-- (/rounds/widget.js → <round-widget>). No monolith code is involved —
-- registration is data.

INSERT INTO dashboards_config.widget_types
    (type, label, description, category, default_props, sort_order)
VALUES (
    'rounds',
    'Round Manager',
    'Processo di consenso iterativo sul Bene',
    'data',
    '{
        "widgetProps": {"title": "Round Manager"},
        "additionalConfig": {
            "remote": {"src": "/rounds/widget.js", "tag": "round-widget"}
        }
    }'::jsonb,
    95
)
ON CONFLICT (type) DO UPDATE
    SET default_props = EXCLUDED.default_props;
