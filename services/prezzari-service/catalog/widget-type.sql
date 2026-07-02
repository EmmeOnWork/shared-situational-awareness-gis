-- Manual catalog registration for the I Prezziari Widget.
--
-- The service self-registers on boot (src/config/catalog_registration.py). Use
-- this SQL instead when REGISTER_IN_CATALOG=false, or when the service's DB role
-- may not write the monolith's `dashboards_config` schema and an operator with
-- rights applies it once. It is the same upsert, kept in sync with that module.
--
-- Effect: the I Prezziari Widget appears in the dashboard "Add widget" menu. The
-- `remote` pointer routes the monolith's generic RemoteWidget seam at this
-- service's UI bundle (/prezzari/widget.js → <prezzari-widget>). No monolith code
-- is involved — registration is data.

INSERT INTO dashboards_config.widget_types
    (type, label, description, category, default_props, sort_order)
VALUES (
    'prezzari',
    'I Prezziari',
    'Locazione OMI del comune cliccato e prezzario lavori Regione Campania',
    'data',
    '{
        "widgetProps": {"title": "I Prezziari"},
        "additionalConfig": {
            "remote": {"src": "/prezzari/widget.js", "tag": "prezzari-widget"}
        }
    }'::jsonb,
    95
)
ON CONFLICT (type) DO UPDATE
    SET default_props = EXCLUDED.default_props;
