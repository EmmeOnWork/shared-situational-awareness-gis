-- Manual catalog registration for the demographic Widget.
--
-- The service self-registers on boot (src/config/catalog_registration.py). Use
-- this SQL instead when REGISTER_IN_CATALOG=false, or when the service's DB role
-- may not write the monolith's `dashboards_config` schema and an operator with
-- rights applies it once. It is the same upsert, kept in sync with that module.
--
-- Effect: the demographic Widget appears in the dashboard "Add widget" menu. The
-- `remote` pointer routes the monolith's generic RemoteWidget seam at this
-- service's UI bundle (/demographics/widget.js → <demographic-widget>). No
-- monolith code is involved — registration is data.

INSERT INTO dashboards_config.widget_types
    (type, label, description, category, default_props, sort_order)
VALUES (
    'demographic',
    'Demografia',
    'Profilo demografico ISTAT per territorio',
    'data',
    '{
        "widgetProps": {"title": "Profilo demografico"},
        "additionalConfig": {
            "remote": {"src": "/demographics/widget.js", "tag": "demographic-widget"}
        }
    }'::jsonb,
    80
)
ON CONFLICT (type) DO UPDATE
    SET default_props = EXCLUDED.default_props;
