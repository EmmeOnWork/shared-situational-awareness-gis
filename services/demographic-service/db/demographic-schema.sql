-- Schema-only DDL for the demographic widget's data table.
--
-- Applied by the compose `demographic-schema-init` one-shot on every bring-up,
-- NOT by the service at runtime: the demographic-service stays a pure reader
-- (ADR-0001), so it never issues DDL. Idempotent (CREATE TABLE IF NOT EXISTS).
--
-- This file creates the EMPTY table only. Loading rows is a separate, manual
-- step (see README.md) — the compose brings up the schema, not the data.
--
-- Shape mirrors data/demographic.csv and the columns the router reads
-- (src/routers/demographics/demographics_router.py): a wide row per Territory,
-- name-keyed, no geometry, no time series. `territory_name` is the lookup key
-- and is unique across all scales, so it is the primary key.

CREATE TABLE IF NOT EXISTS public.demographic (
    territory_name        text PRIMARY KEY,
    territory_name_istat  text,
    level                 text NOT NULL,
    pop_total             double precision,
    pop_italian           double precision,
    pop_foreign           double precision,
    age_share_0_14        double precision,
    age_share_15_64       double precision,
    age_share_65_plus     double precision,
    mig_rate_internal     double precision,
    mig_rate_foreign      double precision,
    mig_rate_total        double precision
);

-- Spatial sidecar for the read-only widget: ONE polygon per Territory we can
-- resolve a map click to. Kept SEPARATE from the (name-keyed, geometry-free)
-- demographic table so that table stays exactly as loaded, while this one holds
-- only what /demographics/at-point needs: a boundary geometry whose name is the
-- SAME key (`territory_name`) so the runtime spatial query is a trivial join.
--
-- Only the province level is needed — provinces tile Italy and are the finest
-- level the demographic data carries, so a land click always lands in exactly
-- one. Loading rows is a separate manual step (run load_boundaries.py, see
-- README.md); the compose brings up the schema, not the data. Requires PostGIS (the compose
-- postgres is postgis/postgis), still no DDL at runtime (ADR-0001).
CREATE TABLE IF NOT EXISTS public.demographic_boundary (
    territory_name  text PRIMARY KEY REFERENCES public.demographic(territory_name),
    level           text NOT NULL,
    geom            geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_demographic_boundary_geom
    ON public.demographic_boundary USING gist (geom);
