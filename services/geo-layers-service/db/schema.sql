-- Schema-only DDL for the geo-layers service's first layer.
--
-- Applied by the compose `geo-layers-schema-init` one-shot on every bring-up,
-- NOT by the service at runtime (ADR-0001: the service never issues DDL).
-- Idempotent (CREATE TABLE IF NOT EXISTS). Creates the EMPTY table only; the
-- civics are loaded separately by db/load_civics.py (see README.md).
--
-- One row per under-1Gb civic address (authoritative EGON/Infratel data):
-- id_egon is the national civic id and the natural primary key; geom is the
-- WGS84 point used to render the (clustered) markers. Requires PostGIS (the
-- compose postgres is postgis/postgis).

CREATE TABLE IF NOT EXISTS public.fixed_network_under_1gb (
    id_egon    bigint PRIMARY KEY,
    regione    text,
    provincia  text,
    procom21   text,
    comune     text,
    frazione   text,
    strada     text,
    civico     text,
    geom       geometry(Point, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fixed_network_under_1gb_geom
    ON public.fixed_network_under_1gb USING gist (geom);

CREATE INDEX IF NOT EXISTS idx_fixed_network_under_1gb_regione
    ON public.fixed_network_under_1gb (regione);
