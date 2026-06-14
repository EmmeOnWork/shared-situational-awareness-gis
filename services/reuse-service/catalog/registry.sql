-- building_workshop — the registry of reuse-POIs (Bene) this service OWNS.
--
-- reuse-service ensures this table on boot (best-effort, IF NOT EXISTS — see
-- src/config/workshop_registry.py). Apply this manually where the service's DB
-- role may not create tables, or to provision the schema ahead of first boot.
--
-- Keyed by the monolith's POI id, referenced **by value only** — no cross-domain
-- FK to public.pois (the monolith owns and re-syncs POIs; a FK would couple our
-- migrations to theirs — ADR-0001 / CONTEXT). master_user_id (the Workshop
-- Master) is anticipated but not modelled in v1.

CREATE TABLE IF NOT EXISTS public.building_workshop (
    poi_id     bigint PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);
