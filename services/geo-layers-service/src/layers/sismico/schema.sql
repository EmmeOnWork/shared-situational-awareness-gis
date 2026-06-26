-- Schema-only DDL for the sismico (seismic risk) layer.
--
-- Applied by the compose `geo-layers-schema-init` one-shot (ADR-0001: no DDL at
-- runtime). Idempotent. Creates the EMPTY table.
--
-- The seismic CSV is a per-comune classification with NO geometry. The /sismico
-- route draws the clicked comune's boundary from public.areas (area_type_id = 3) and
-- colours it by ZONA_SISMICA from this table, joined on the comune ISTAT code
-- (areas.metadata->>'ref:ISTAT'). So NO separate comuni-boundary import is needed —
-- the layer renders for exactly the comuni public.areas has. Load this table with
-- the layer's load.py (see the service README).

CREATE TABLE IF NOT EXISTS public.seismic_zone (
    cod_istat  integer PRIMARY KEY,
    zona       text NOT NULL          -- 1, 2, 3, 3S, 4
);
