-- Schema + grants for I Prezziari's Prezzario dei Lavori snapshot table (task 03).
--
-- Applied by the compose `prezzari-schema-init` one-shot on bring-up, NOT by the
-- service at runtime: the DDL comes up with the compose, so the service only ever
-- issues DML (the offline ingest replaces the snapshot; the data route reads it).
-- Mirrors the likert/round pattern. Idempotent (CREATE TABLE IF NOT EXISTS; grants
-- re-asserted), loads NO data — the table is a STATIC, DISPOSABLE snapshot,
-- re-buildable from the source publication by the offline ingest.
--
-- I Prezziari owns static versioned snapshots (prezzari ADR-0001): no refresh
-- worker, no TTL, no runtime egress. Reads only its own table here; the monolith's
-- geography (for the OMI list) is read by id/name only elsewhere. Lives in shared
-- `public` (ADR-0001).

-- The DB role this service connects as, which needs the DML grants below. The
-- compose one-shot passes it (`-v service_role=...`, default the local `janus`);
-- default it here too so the file also runs standalone via `psql -f`.
\if :{?service_role}
\else
\set service_role janus
\endif

-- The curated Prezzario dei Lavori: one row per Voce of the renovation/recovery
-- slice of the Regione Campania price list. `codice` is the Voce code and PK.
-- `capitolo` is the chapter it belongs to (derived from the codice at ingest) and
-- `capitolo_titolo` its human title, denormalized onto every row so the data route
-- lists the chapters without a second table (latest-only ⇒ a chapter's title is
-- stable within the snapshot). `publication` is the edition stamp (e.g. "2026");
-- latest-only, so the whole table is replaced on re-ingest — no history column.
CREATE TABLE IF NOT EXISTS public.prezzario_voci (
    codice          text NOT NULL,
    descrizione     text NOT NULL,
    um              text NOT NULL,
    prezzo          double precision NOT NULL,
    capitolo        text NOT NULL,
    capitolo_titolo text NOT NULL,
    publication     text NOT NULL,
    PRIMARY KEY (codice)
);

-- The data route navigates by Capitolo; index it so the chapter list and any
-- chapter filter stay cheap as the curated slice grows.
CREATE INDEX IF NOT EXISTS idx_prezzario_voci_capitolo
    ON public.prezzario_voci (capitolo);

-- The offline ingest replaces the snapshot (DELETE + INSERT, latest-only); the data
-- route only SELECTs. DELETE is granted because re-ingest wipes the prior edition.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.prezzario_voci TO :"service_role";


-- The OMI locazione snapshot (task 04 — Lista A, Prezziario di Locazione): one row
-- per comune × Zona OMI × tipologia × stato of the Agenzia delle Entrate OMI rental
-- quotations, Campania comuni only, locazione (rent) values only. `region_id` is the
-- monolith region the comune maps to (referenced BY ID only, no FK to the monolith's
-- table — shared DB, ADR-0001); the offline ingest resolves each OMI comune's ISTAT
-- code to it. `canone_min`/`canone_max` are the min–max monthly rent, `um` its unit
-- (€/m²/mese). `publication` is the semestral edition stamp (e.g. "2025 · II
-- semestre"); latest-only, so the whole table is replaced on re-ingest.
CREATE TABLE IF NOT EXISTS public.omi_locazione (
    region_id    integer NOT NULL,
    zona         text NOT NULL,
    tipologia    text NOT NULL,
    stato        text NOT NULL,
    canone_min   double precision NOT NULL,
    canone_max   double precision NOT NULL,
    um           text NOT NULL,
    publication  text NOT NULL
);

-- The data route reads a single comune's rows (WHERE region_id = :region_id) on every
-- click; index it so that comune-scoped read stays cheap as all Campania comuni land.
CREATE INDEX IF NOT EXISTS idx_omi_locazione_region_id
    ON public.omi_locazione (region_id);

-- Same latest-only lifecycle as prezzario_voci: the offline ingest DELETE+INSERTs the
-- whole snapshot; the data route only SELECTs.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.omi_locazione TO :"service_role";
