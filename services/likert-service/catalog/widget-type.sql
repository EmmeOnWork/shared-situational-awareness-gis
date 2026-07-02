-- Manual catalog registration for the Scala Likert Widget.
--
-- The service self-registers on boot (src/config/catalog_registration.py). Use
-- this SQL instead when REGISTER_IN_CATALOG=false, or when the service's DB role
-- may not write the monolith's `dashboards_config` schema and an operator with
-- rights applies it once. It is the same upsert, kept in sync with that module.
--
-- Effect: the Scala Likert Widget appears in the dashboard "Add widget" menu.
-- The `remote` pointer routes the monolith's generic RemoteWidget seam at this
-- service's UI bundle (/likert/widget.js → <likert-widget>). No monolith code is
-- involved — registration is data.

INSERT INTO dashboards_config.widget_types
    (type, label, description, category, default_props, sort_order, allowed_roles)
VALUES (
    'likert',
    'Scala Likert',
    'Gradimento locale della Vocazione attiva sul comune cliccato',
    'data',
    '{
        "widgetProps": {"title": "Scala Likert"},
        "additionalConfig": {
            "remote": {"src": "/likert/widget.js", "tag": "likert-widget"}
        }
    }'::jsonb,
    96,
    -- Role-based visibility (stakeholder_role): relevant to institutional and
    -- economic stakeholders, not the technical one. NULL would mean "all roles".
    '{istituzionale,economico}'::text[]
)
ON CONFLICT (type) DO UPDATE
    SET default_props = EXCLUDED.default_props,
        allowed_roles = EXCLUDED.allowed_roles;
