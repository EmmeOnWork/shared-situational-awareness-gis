-- Schema + grants for the Round Manager's durable record (task 05).
--
-- Applied by the compose `round-schema-init` one-shot on every bring-up, NOT by
-- the service at runtime: the schema (DDL) comes up with the compose, so the
-- service only ever issues DML (an idempotent upsert per closed Round). Mirrors
-- the characteristic-service pattern. Idempotent (CREATE TABLE IF NOT EXISTS;
-- grant re-asserted), loads NO data.
--
-- This Widget is the first to OWN write state. The live round process (lobby,
-- votes, tally) is in-memory and realtime; only the CLOSED Round's outcome is
-- persisted here — raw per-(Role × Vocazione) counts, N, per-Role + overall
-- Consensus and the Round's duration — so the measure is re-derivable offline and
-- trends are analysable. `poi_id` is the monolith POI id (the Bene), referenced BY
-- ID ONLY (no cross-domain FK into public.pois; the monolith re-syncs those rows).

-- The DB role this service connects as, which needs the DML grant below. The
-- compose one-shot passes it (`-v service_role=...`, default the local `janus`);
-- default it here too so the file also runs standalone via `psql -f`.
\if :{?service_role}
\else
\set service_role janus
\endif

-- One row per closed Round of a Bene, keyed by (poi_id, round_number). A re-close
-- (e.g. a replay) is an idempotent upsert. The two consensus columns are JSONB so
-- the per-Role branches stay queryable without a child table.
CREATE TABLE IF NOT EXISTS public.round_outcomes (
    poi_id              integer NOT NULL,
    round_number        integer NOT NULL,
    n                   integer NOT NULL,
    votes_by_role       jsonb   NOT NULL,
    per_role_consensus  jsonb   NOT NULL,
    overall_consensus   double precision NOT NULL,
    duration_seconds    double precision,
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (poi_id, round_number)
);

CREATE INDEX IF NOT EXISTS idx_round_outcomes_poi_id
    ON public.round_outcomes (poi_id);

-- The service writes the outcome on close (INSERT ... ON CONFLICT DO UPDATE) and
-- the recap may read history; no DELETE (a Round's record is immutable history).
GRANT SELECT, INSERT, UPDATE ON public.round_outcomes TO :"service_role";
