# likert-service — db

`likert-schema.sql` is the schema-only DDL (plus DML grants) for this service's
two owned `likert_*` tables. It is applied by the compose `likert-schema-init`
one-shot on every bring-up — **not** by the service at runtime — so the service
only ever issues DML, never DDL.

It creates two empty tables (the PRD data model; service ADR-0001):

- `likert_poi_place(poi_id PK, google_place_id, match_confidence, no_match,
  matched_at)` — the **permanent** POI→Google identity map. Resolved once per POI
  and kept forever (ToS-allowed); `no_match=true` records the unmatchable so the
  refresh worker doesn't re-resolve it every cycle.
- `likert_place_rating(google_place_id PK, rating, user_ratings_total,
  fetched_at)` — the TTL'd ratings **cache**: a place's 1–5 average and review
  count, the two numbers the pooled-mean Gradimento weighs. `fetched_at` drives
  the ≤30-day TTL and the widget's "aggiornato il …".

Both are a **derived, disposable** cache, fully re-buildable from Google by the
refresh worker — the Scala Likert is a read widget that unusually owns cache
state (like round-service). The data route reads **only** these tables; it never
makes a live Google call on a widget request.

The script grants the service's DB role `SELECT/INSERT/UPDATE` (the worker
upserts, the route reads — no `DELETE`, a stale row is overwritten in place). The
role defaults to the local `janus`; the compose one-shot passes the real one via
`-v service_role=...`.

`poi_id` references `public.pois(id)` **by id only** — no cross-domain FK into the
monolith's `pois` (it re-syncs those rows; ADR-0001).

Idempotent: re-running it on an existing database is a no-op (`CREATE TABLE IF
NOT EXISTS`; grants are re-asserted; loads no data).
