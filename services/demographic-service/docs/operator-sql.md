# Operator SQL — enabling `demographics:read`

This is a **data step**, not part of the service code. The demographic service
only *verifies* tokens and *enforces* the `demographics:read` scope; it never
writes to `scopes` or `role_scopes`. To actually let a role through the guard,
an operator must register the scope and grant it in the **shared** database
(ADR-0001: "don't touch the monolith" means its *code*, not its *data*).

Run once against the shared Supabase Postgres database:

```sql
-- 1. Register the scope (idempotent).
INSERT INTO public.scopes (name, description)
VALUES ('demographics:read', 'Read aggregated ISTAT demographic data')
ON CONFLICT (name) DO NOTHING;

-- 2. Grant it to the role(s) that should reach the widget, e.g. VIEWER.
--    Adjust the role name(s) to your deployment.
INSERT INTO public.role_scopes (role_id, scope_id)
SELECT r.id, s.id
FROM public.roles r
CROSS JOIN public.scopes s
WHERE upper(r.name) = 'VIEWER'
  AND s.name = 'demographics:read'
ON CONFLICT DO NOTHING;
```

After this, the monolith mints access tokens whose `scope` claim includes
`demographics:read` for the granted role(s), and this service's guard admits
them. No service restart is required — the scope is read from each token.

> Note: column names (`scopes.description`, the `role_scopes` PK) follow the
> monolith's shared schema. If they differ in your environment, adapt the SQL;
> the conflict targets are the only environment-specific part.
