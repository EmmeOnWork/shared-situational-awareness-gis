# Building data lives in `building_*` tables, never inside the monolith's `pois`

The Scheda and Blueprints for a Bene are stored in this service's own tables in
`public` (`building_workshop`, `building_scheda`, `building_blueprint`); the
monolith's `pois` table is referenced by `poi_id` only — **never written, no
column added, no `metadata` reuse, no cross-domain FK**. This mirrors the
demographic service's deliberate "reference the monolith by id/name, build no FK
into it yet" stance (ADR-0001).

## Considered options

- **Store the Scheda in `pois.metadata` (jsonb) and add a blueprint column to
  `pois`.** Tempting — it looks like fewer tables and one less join — and was
  actively proposed. Rejected: POIs are **re-synced from external sources**
  (`source = foursquare | google_place`, `date_refreshed`), so the monolith owns
  and periodically rewrites those rows; our reuse data piggybacked there would be
  silently overwritten. It also violates the standing invariant that a Widget
  never writes the monolith's tables, and dragging `bytea` into `pois` would
  weigh down every map query that touches POIs.

## Consequences

- Reads are a PK lookup (`building_scheda.poi_id`) plus an indexed query
  (`building_blueprint.poi_id`) — trivial at this volume; "more tables" is not a
  performance cost here.
- Frontend speed comes from keeping the light list (sezioni) separate from the
  heavy `bytea`, served by id (`GET /characteristic/blueprints/{id}`) and loaded only
  when a Sezione is shown — not from minimising table count.
- A future `poi_id → pois(id)` FK remains possible but is intentionally not built
  yet, consistent with ADR-0001.
