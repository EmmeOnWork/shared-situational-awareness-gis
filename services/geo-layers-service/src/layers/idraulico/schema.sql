-- Schema-only DDL for the idraulico (hydraulic/flood hazard) layer.
--
-- Applied by the compose `geo-layers-schema-init` one-shot (ADR-0001: no DDL at
-- runtime). Idempotent. Creates the EMPTY table; the three ISPRA scenarios
-- (bassa/media/elevata) are loaded once with ogr2ogr — reprojected from EPSG:3035
-- to 4326 and Campania-clipped (see the service README). The /idraulico route
-- simplifies + dissolves per level at serve time.
--
-- `scenario` is the raw ISPRA scenario string (constant per source file); the
-- router maps it to `livello` (bassa/media/elevata). Requires PostGIS.

CREATE TABLE IF NOT EXISTS public.idraulico_pericolosita (
    gid       bigserial PRIMARY KEY,
    scenario  text,
    geom      geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idraulico_pericolosita_geom
    ON public.idraulico_pericolosita USING gist (geom);
