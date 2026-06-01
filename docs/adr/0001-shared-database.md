# Demographic microservice shares the monolith's Supabase database

Status: accepted

The demographic widget is built as a separate FastAPI deployable (to separate
the work from the Janus monolith and avoid touching its code), but it reads and
writes the **same Supabase Postgres/PostGIS database** the monolith uses, rather
than owning its own datastore. Its `demographic` table lives in the shared
`public` schema next to the monolith's tables, and it authenticates by verifying
the monolith-issued JWTs with the shared verification key.

## Considered options

- **Own database per service** (textbook microservice). Rejected: it would
  duplicate the territory/geography data, force cross-database joins or data
  sync, and add infrastructure for a single read-mostly table.
- **A module inside the monolith.** Rejected: the explicit goal is to develop
  and deploy this work separately without modifying the monolith repo.
- **Shared database (chosen).** No duplication, a single source of truth,
  fastest to ship, and trivially enables the anticipated `territory_name →
  regions` foreign key.

## Consequences

- The two services are **coupled at the data layer**: a monolith change to a
  table the microservice reads (e.g. `regions`, `scopes`) can break it, with no
  compile-time signal. Treat the shared schema as a contract.
- "Don't touch the monolith" means its **code**, not its **data**: enabling
  `demographics:read` requires inserting a row into the shared `scopes` table and
  granting it via `role_scopes`.
- This is **hard to reverse** once the table is populated and the read query is
  in production — splitting to an owned database later means a data migration and
  a sync strategy.
