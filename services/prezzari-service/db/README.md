# prezzari-service — db

`prezzari-schema.sql` is the schema-only DDL (plus DML grants) for this service's
owned snapshot tables. It is applied by the compose `prezzari-schema-init` one-shot
on every bring-up — **not** by the service at runtime — so the service only ever
issues DML, never DDL. Idempotent (`CREATE TABLE IF NOT EXISTS`; grants re-asserted;
loads no data).

## `prezzario_voci` (task 03 — Lista B, Prezzario dei Lavori)

The curated slice of the **Regione Campania** public-works price list, limited to the
**renovation / recovery Capitoli**. One row per **Voce**:

- `codice` (PK) — the Voce code, e.g. `E.01.010.a`.
- `descrizione`, `um`, `prezzo` — the line's description, unit of measure and unit
  price (the columns the right column renders).
- `capitolo` — the chapter code (derived from `codice`'s leading segment at ingest),
  indexed for the Capitolo nav/filter.
- `capitolo_titolo` — the chapter's human title, **denormalized** onto every row so
  the data route lists the chapters without a second table (safe under latest-only:
  a chapter's title is constant within one snapshot).
- `publication` — the edition stamp (e.g. `2026`). **Latest-only**: re-ingesting
  **replaces** the whole snapshot, so there is exactly one edition and no history
  column.

It is a **static, disposable** snapshot (prezzari ADR-0001) — no refresh worker, no
TTL, no runtime egress — fully re-buildable from the source publication by the
offline ingest (`ingest_prezzario.py`). The data route reads **only** this table.

### Ingest (offline, latest-only)

`ingest_prezzario.py` parses a source export into the curated rows and **replaces**
the prior snapshot (DELETE + INSERT in one transaction). Its load-bearing parse +
curation logic lives in the tested pure module
`src/routers/prezzari/prezzario_parser.py` (`parse_voci` / `CURATED_CAPITOLI`); the
CLI is thin orchestration around it (manual-verify).

```
docker compose cp services/prezzari-service/db/ingest_prezzario.py \
    prezzari-service:/tmp/ingest_prezzario.py
docker compose cp prezzario-2026.csv prezzari-service:/tmp/prezzario-2026.csv
docker compose exec prezzari-service \
    python /tmp/ingest_prezzario.py /tmp/prezzario-2026.csv --publication 2026
```

The grant includes `DELETE` because a re-ingest wipes the prior edition before
loading the new one.

The **curated Capitolo set is editorial** (`CURATED_CAPITOLI` in the parser): which
chapters count as renovation/recovery is a human decision re-confirmed per edition,
not inferred at runtime.

## `omi_locazione` (task 04 — Lista A, Prezziario di Locazione)

The Agenzia delle Entrate **OMI** rental quotations, **Campania comuni only** and
**locazione (rent) only** — the OMI sale (compravendita) values are dropped on purpose
(CONTEXT.md). One row per **comune × Zona OMI × tipologia × stato**:

- `region_id` — the monolith **region** the comune maps to (referenced **by id only**,
  no FK to the monolith; shared DB, ADR-0001). The data route reads a comune's rows by
  this id (`WHERE region_id = :region_id`), so it is **indexed**.
- `zona`, `tipologia`, `stato` — the Zona OMI, the property tipologia and its stato
  (the left column's row key). The Widget lists **all** the comune's Zone OMI; it does
  not resolve the click to one zona (that would need OMI zone geometries — out of scope).
- `canone_min`, `canone_max`, `um` — the min–max monthly rent and its unit
  (`€/m²/mese`).
- `publication` — the semestral edition stamp (e.g. `2025 · II semestre`).
  **Latest-only**: re-ingesting **replaces** the whole snapshot, so there is exactly one
  edition and no history column.

Same **static, disposable** snapshot lifecycle as `prezzario_voci` — re-buildable from
the source OMI publication by the offline ingest (`ingest_omi.py`). The data route reads
**only** this table; the comune geography is resolved elsewhere and referenced by id.

### Ingest (offline, Campania-scoped, latest-only)

`ingest_omi.py` parses an OMI source export into the Campania locazione rows and
**replaces** the prior snapshot (DELETE + INSERT in one transaction). Its load-bearing
parse + Campania/locazione filtering lives in the tested pure module
`src/routers/prezzari/omi_parser.py` (`parse_omi` / `CAMPANIA_PROVINCE`). The CLI adds
the one thing the pure parser cannot do — map each OMI comune's **ISTAT code** to its
monolith `region_id` (via `areas.metadata->>'ref:ISTAT'` on the comune boundaries,
`area_type_id = 3`); rows whose ISTAT does not resolve to a Campania region are skipped.

```
docker compose cp services/prezzari-service/db/ingest_omi.py \
    prezzari-service:/tmp/ingest_omi.py
docker compose cp omi-2025-s2.csv prezzari-service:/tmp/omi-2025-s2.csv
docker compose exec prezzari-service \
    python /tmp/ingest_omi.py /tmp/omi-2025-s2.csv --publication "2025 · II semestre"
```

The grant includes `DELETE` because a re-ingest wipes the prior edition before loading
the new one.

The **Campania province set is editorial** (`CAMPANIA_PROVINCE` in the parser): which
provinces count as Campania is fixed explicitly, not inferred at runtime.
