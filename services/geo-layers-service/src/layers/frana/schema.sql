-- Schema-only DDL for the frana (landslide hazard) layer.
--
-- Applied by the compose `geo-layers-schema-init` one-shot (ADR-0001: no DDL at
-- runtime). Idempotent. Creates the EMPTY table; the polygons are loaded once
-- with ogr2ogr (Campania-clipped + area-filtered — see the service README). The
-- /frana route simplifies + dissolves per class at serve time.
--
-- One row per landslide-hazard area (ISPRA PAI mosaic). `per_fr_ita` is the
-- hazard-class label ("Aree di Attenzione AA", "Moderata P1" … "Molto elevata
-- P4"); the router exposes its trailing code (AA/P1..P4) as `classe`. `gid` is a
-- surrogate key so ogr2ogr can `-append` with `-unsetFid`. Requires PostGIS.

CREATE TABLE IF NOT EXISTS public.frana_pericolosita (
    gid         bigserial PRIMARY KEY,
    per_fr_ita  text,
    geom        geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_frana_pericolosita_geom
    ON public.frana_pericolosita USING gist (geom);
