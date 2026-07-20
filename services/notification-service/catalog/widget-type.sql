-- Manual catalog registration — the same row notification-service upserts on
-- boot (src/config/catalog_registration.py). Apply this where REGISTER_IN_CATALOG
-- is off or the service's DB role may not write the monolith's schema, so the
-- Realtime Notifier is still picked up by the dashboard's overlay seam.
--
-- Unlike the card Widgets, this row is flagged for the page-global overlay seam
-- `default_props.placement = "overlay"` tells the monolith's generic
-- <RemoteOverlay> loader to mount the bundle chromeless and page-global, not as a
-- grid card. The renderer still routes on `remote`: {src} is the unguarded bundle
-- route, {tag} the custom element <notification-overlay> defines. On conflict we
-- refresh only the code-owned default_props, leaving operator-owned presentation
-- columns be — the same upsert shape the monolith uses for its own seed rows.

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
    'notifications',
    'Notifiche in tempo reale',
    'Avvisi live del laboratorio (toast + audio), in sovrimpressione',
    'data',
    '{
        "placement": "overlay",
        "additionalConfig": {"remote": {"src": "/notifications/widget.js", "tag": "notification-overlay"}}
    }'::jsonb,
    90
)
ON CONFLICT (type) DO UPDATE
    SET default_props = EXCLUDED.default_props;
