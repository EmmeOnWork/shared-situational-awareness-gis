# characteristic-service — db

`characteristic-schema.sql` is the schema-only DDL (plus DML grants) for this
service's `building_*` tables. It is applied by the compose
`characteristic-schema-init` one-shot on every bring-up — **not** by the service
at runtime — so the service only ever issues DML, never DDL.

It creates three empty tables (this context's ADR-0001 + the PRD data model):

- `building_workshop(poi_id, created_at)` — the Bene registry (owned by
  reuse-service; this service reads it, fallback-upserts on first write).
- `building_scheda(poi_id → building_workshop, …)` — one Scheda per Bene.
- `building_blueprint(id, poi_id → building_workshop, sezione, image bytea, …,
  UNIQUE(poi_id, sezione))` — N per Bene, one per Sezione.

Unlike the read-only demographic service this one **writes**, so the script also
grants the service's DB role `INSERT/UPDATE/DELETE` on those tables (and `USAGE`
on the blueprint id sequence). The role defaults to the local `janus`; the
compose one-shot passes the real one via `-v service_role=...`.

`poi_id` references `public.pois(id)` **by id only** — no cross-domain FK into the
monolith's `pois` (it re-syncs those rows; this context's ADR-0001). FKs *among*
the `building_*` tables are intra-domain and fine.

Idempotent: re-running it on an existing database is a no-op (`CREATE TABLE IF
NOT EXISTS`; grants are re-asserted).
