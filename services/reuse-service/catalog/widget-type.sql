-- Manual catalog registration — the same row reuse-service upserts on boot
-- (src/config/catalog_registration.py). Apply this where REGISTER_IN_CATALOG is
-- off or the service's DB role may not write the monolith's schema, so the
-- Workshop Selector still appears in the dashboard "Add widget" menu as data.
--
-- The renderer routes on `remote`: {src} is the unguarded bundle route, {tag}
-- the custom element <reuse-widget> defines. On conflict we refresh only the
-- code-owned default_props, leaving operator-owned presentation columns be —
-- the same upsert shape the monolith uses for its own seed rows.

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

INSERT INTO dashboards_config.widget_types
    (type, label, description, category, default_props, sort_order)
VALUES (
    'reuse',
    'Selettore Bene',
    'Seleziona il Bene attivo (Workshop) e centra la mappa',
    'data',
    '{
        "widgetProps": {"title": "Bene"},
        "additionalConfig": {"remote": {"src": "/reuse/widget.js", "tag": "reuse-widget"}}
    }'::jsonb,
    10
)
ON CONFLICT (type) DO UPDATE
    SET default_props = EXCLUDED.default_props;
