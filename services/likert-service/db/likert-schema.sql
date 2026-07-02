-- Schema + grants for the Scala Likert's two owned tables (task 04).
--
-- Applied by the compose `likert-schema-init` one-shot on bring-up, NOT by the
-- service at runtime: the DDL comes up with the compose, so the service only ever
-- issues DML (the refresh worker upserts the cache; the data route reads it).
-- Mirrors the round-service pattern. Idempotent (CREATE TABLE IF NOT EXISTS; grants
-- re-asserted), loads NO data — both tables are a DERIVED, DISPOSABLE cache,
-- re-buildable from Google by the refresh worker.
--
-- The Scala Likert is a read widget that — unusually — OWNS cache state (like
-- round-service). It reads the monolith's POIs by id only (no cross-domain FK into
-- public.pois; the monolith re-syncs those rows). Both tables live in shared
-- `public` (ADR-0001).

-- The DB role this service connects as, which needs the DML grants below. The
-- compose one-shot passes it (`-v service_role=...`, default the local `janus`);
-- default it here too so the file also runs standalone via `psql -f`.
\if :{?service_role}
\else
\set service_role janus
\endif

-- The PERMANENT POI→Google identity map. One row per competitor POI ever resolved:
-- its `google_place_id` (nullable) once matched, the match confidence, and a
-- `no_match` flag so the worker doesn't burn calls re-resolving the unmatchable
-- every cycle. `poi_id` is the monolith POI id, referenced BY ID ONLY. Resolved
-- once and kept forever (ToS-allowed), so a place is matched only once.
CREATE TABLE IF NOT EXISTS public.likert_poi_place (
    poi_id           integer NOT NULL,
    google_place_id  text,
    match_confidence double precision,
    no_match         boolean NOT NULL DEFAULT false,
    matched_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (poi_id)
);

-- The TTL'd ratings CACHE, keyed by the resolved Google place. `rating` is the
-- place's 1–5 average and `user_ratings_total` its review count — the two numbers
-- the pooled-mean Gradimento weighs. `fetched_at` drives both the ≤30-day TTL (the
-- ToS caching ceiling, enforced by the refresh worker) and the widget's
-- "aggiornato il …". The data route reads ONLY this table — never a live Google
-- call on a widget request.
CREATE TABLE IF NOT EXISTS public.likert_place_rating (
    google_place_id    text NOT NULL,
    rating             double precision NOT NULL,
    user_ratings_total integer NOT NULL,
    fetched_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (google_place_id)
);

-- The data route joins competitor POIs → identity map → cache to pool the ratings;
-- index the join column so that read stays cheap as the cache grows.
CREATE INDEX IF NOT EXISTS idx_likert_poi_place_google_place_id
    ON public.likert_poi_place (google_place_id);

-- The worker upserts both tables (resolve identities, refresh ratings); the data
-- route only SELECTs. No DELETE — a stale row is overwritten in place, never
-- removed (the cache is rebuilt by upsert, not by purge).
GRANT SELECT, INSERT, UPDATE ON public.likert_poi_place   TO :"service_role";
GRANT SELECT, INSERT, UPDATE ON public.likert_place_rating TO :"service_role";
