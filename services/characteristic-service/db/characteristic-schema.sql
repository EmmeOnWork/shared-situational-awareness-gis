-- Schema + grants for the characteristic widget's data tables.
--
-- Applied by the compose `characteristic-schema-init` one-shot on every bring-up,
-- NOT by the service at runtime: the schema (DDL) comes up with the compose, so
-- the service only ever issues DML. Idempotent (CREATE TABLE / GRANT IF NOT
-- EXISTS semantics), creates the three EMPTY tables and grants the service's DB
-- role write access to them.
--
-- Unlike the read-only demographic service, this service WRITES (Blueprint +
-- Scheda upload/edit/delete), so its DB role needs INSERT/UPDATE/DELETE here.
-- The Workshop Master *authorization* gate (a write scope + per-POI ownership) is
-- a separate, deferred concern at the app layer — this grant is only the DB-level
-- permission for the connection role.
--
-- Data model: this context's ADR-0001 (Building data lives in `building_*`, never
-- in the monolith's `pois`) + the PRD data model. `poi_id` references
-- public.pois(id) BY ID ONLY — no cross-domain FK into `pois` (the monolith
-- re-syncs those rows). FKs AMONG the building_* tables are intra-domain and fine.

-- The DB role this service connects as, which needs the DML grants below. The
-- compose one-shot passes it (`-v service_role=...`, default the local `janus`);
-- default it here too so the file also runs standalone via `psql -f`.
\if :{?service_role}
\else
\set service_role janus
\endif

-- Bene registry: the canonical list of reuse-POIs the Selector reads. Owned and
-- curated by reuse-service; this service reads it and, as a fallback only,
-- upserts a row on first write (auto-register). `poi_id` is the monolith POI id.
CREATE TABLE IF NOT EXISTS public.building_workshop (
    poi_id      integer PRIMARY KEY,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- The Scheda di Individuazione Immobile — exactly one per Bene (1:1 with the
-- Workshop). Enum-like fields (titolo, stato_uso, condizioni, vincoli) are
-- validated in the app, not constrained here, so the legacy/standard layouts map
-- in without DDL churn. All fields are optional/non-blocking (the first Load may
-- save a Blueprint with the Scheda left empty).
CREATE TABLE IF NOT EXISTS public.building_scheda (
    poi_id              integer PRIMARY KEY
                        REFERENCES public.building_workshop(poi_id) ON DELETE CASCADE,
    denominazione       text,
    destinazione_uso    text,
    titolo              text,
    titolo_estremi      text,
    stato_uso           text,
    condizioni          text,
    stato_descrizione   text,
    vincoli             text[],
    vincoli_note        text,
    foglio              text,
    particella          text,
    referente_nome      text,
    referente_email     text,
    referente_tel       text,
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- Blueprints: N per Bene, exactly one per Sezione. Bytes stored as `bytea` in
-- `public` (this context's ADR-0001, decision A) and served by id so the light
-- list never carries the image. Re-upload of a Sezione is a replace, enforced by
-- the UNIQUE(poi_id, sezione).
CREATE TABLE IF NOT EXISTS public.building_blueprint (
    id            bigserial PRIMARY KEY,
    poi_id        integer NOT NULL
                  REFERENCES public.building_workshop(poi_id) ON DELETE CASCADE,
    sezione       text NOT NULL,
    image         bytea NOT NULL,
    content_type  text NOT NULL,
    byte_size     integer NOT NULL,
    uploaded_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (poi_id, sezione)
);

CREATE INDEX IF NOT EXISTS idx_building_blueprint_poi_id
    ON public.building_blueprint (poi_id);

-- Grant the service's DB role write access. This is the one place this service
-- diverges from the read-only demographic pattern. The bigserial needs USAGE on
-- its sequence for INSERTs to allocate ids.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.building_workshop  TO :"service_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON public.building_scheda     TO :"service_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON public.building_blueprint  TO :"service_role";
GRANT USAGE, SELECT ON SEQUENCE public.building_blueprint_id_seq   TO :"service_role";
