# I Prezziari

**What it is** — A read-only Widget in the strangler-fig stack (gateway prefix
`/prezzari`, custom element `<prezzari-widget>`) that renders two static
reference price lists side by side — comune-scoped, ignoring the Active
Workshop — so a user can reason about the economic pre-feasibility of reusing
a building.

**When to read it** — when you're building or touching this widget.

## How it works

I Prezziari is a **consultation surface, not a calculator**: it presents two
raw published price lists next to each other and lets the user weigh them by
eye. It computes nothing and merges nothing — no totals, no break-even, no
quantity selection — and the two pans even carry incompatible units (€/m²/month
vs €/unit-of-work), which is exactly why no automatic formula is offered. It
reads only its own snapshot tables, never calls the source sites at runtime,
and never edits the monolith.

### Left — Prezziario di Locazione (Lista A, OMI)

Sourced from the Agenzia delle Entrate OMI. For the **clicked comune**, lists
every **Zona OMI × building typology × conservation state** with its min–max
**canone** in €/m²/month — the market-rent pan. Only **locazione** (rental)
values are kept; the OMI **compravendita** (sale) values are deliberately
dropped, since reuse keeps and lets the Bene rather than selling it. Shown at
**comune granularity**: all of the comune's Zone OMI are listed as rows — the
click is not resolved down to a single zona (that would need the OMI zone
geometries, which is out of scope).

`GET /prezzari/locazione?lat&lng` — comune-scoped, updates on click; backed by
its own repository over the `omi_locazione` table.

### Right — Prezzario dei Lavori (Lista B, Regione Campania)

A curated slice of the Regione Campania public-works price list, limited to
the **building renovation/recovery** chapters (roads, aqueducts etc. are
excluded). Each **Voce** carries a `codice`, `descrizione`, `unità di misura`
and `prezzo unitario`; a **Capitolo** (e.g. `A03`) groups Voci, and the widget
is navigable by Capitolo with a text search over the descriptions. It is
**region-wide** — identical everywhere in Campania — so it renders on mount and
does not change with the clicked comune.

`GET /prezzari/lavori?capitolo?&q?` — region-fixed; backed by its own
repository over the `prezzario_voci` table.

### Comune resolution

The clicked point arrives as the host-set `lat`/`lng` (the same point every
widget receives); I Prezziari resolves it to a monolith **region**
(`area_type_id = 3`) itself, exactly like the Scala Likert. Lista A's rows are
scoped to this comune; Lista B ignores it entirely, so two Beni in the same
comune see identical figures — geography, not the Bene, is the axis. Like the
Scala Likert, and unlike Building Characteristic or the Round Manager, this
widget is **not sensitive**: it does not consume the Active Workshop.

### Static, versioned snapshots

Both lists are published, slow-moving reference data (OMI **semestral**,
Campania prezzario **annual** — current edition 2026), held as static
versioned snapshots in the widget's own tables and ingested offline; the
widget makes no runtime calls to the source sites. See
[ADR-0001](adr/0001-price-lists-as-static-versioned-snapshots.md) for why.
Each snapshot carries its **publication label**, but only the **latest** of
each list is shown — there is no historical comparison; a new edition is
re-ingested manually, replacing the previous one wholesale.

A few resulting behaviors worth knowing:

- **The click reaction is asymmetric by design**: Lista A updates with the
  comune; Lista B stands still.
- **The two lists degrade independently**: a comune with no published OMI
  shows "quotazioni OMI non disponibili per questo comune" on the left while
  Lista B stays visible on the right.
- **The OMI snapshot is Campania-only**: although OMI is national, only
  Campania comuni are ingested, to match the region-bound Lista B and the
  Campania-bound map; a click outside Campania resolves to no comune (a
  neutral initial state).

## Running it

### Layout

- `src/app.py` — FastAPI: `/health`, the unguarded `/prezzari/widget.js`
  bundle (`Cache-Control: no-cache`), and the two JWT-guarded data routes.
- `src/routers/prezzari/prezzari_router.py` — the two routes above, each
  backed by its own repository over the snapshot tables.
- `src/security/`, `src/config/` — copied JWT verify + shared-DB helper +
  Settings + best-effort catalog self-registration (`type='prezzari'`).
- `ui/` — the `<prezzari-widget>` custom element (two-column layout), built
  to `src/static/prezzari-widget.js` and served by the app.
- `catalog/widget-type.sql` — manual catalog registration fallback.

### Build, test, run

```sh
make ui        # build the <prezzari-widget> bundle into src/static/
make run       # uvicorn on :28008 (through the gateway at /prezzari)
make test      # pytest — the standard service suite
```

The whole stack builds/deploys via
`docker compose build prezzari-service && up -d prezzari-service` (UI baked
into the image; no dev bind-mount).

### Snapshot tables and offline ingestion

`prezzari-schema.sql` is the schema-only DDL (plus DML grants) for the two
owned snapshot tables below. It's applied by the compose
`prezzari-schema-init` one-shot on every bring-up — **not** by the service at
runtime — so the service only ever issues DML, never DDL. It's idempotent
(`CREATE TABLE IF NOT EXISTS`; grants re-asserted; loads no data). Both
tables' grants include `DELETE`, since a re-ingest wipes the prior edition
before loading the new one.

**`prezzario_voci`** (Lista B) — one row per Voce: `codice` (PK, e.g.
`E.01.010.a`), `descrizione`/`um`/`prezzo`, `capitolo` (derived from
`codice`'s leading segment at ingest, indexed for the nav/filter),
`capitolo_titolo` (the chapter's human title, denormalized onto every row —
safe under latest-only), `publication` (edition stamp, e.g. `2026`).
Latest-only: re-ingesting **replaces** the whole snapshot (DELETE + INSERT in
one transaction) via `ingest_prezzario.py`. The load-bearing parse + curation
logic lives in the tested pure module
`src/routers/prezzari/prezzario_parser.py` (`parse_voci` /
`CURATED_CAPITOLI`); the CLI is thin orchestration around it (manual-verify).
The curated Capitolo set (`CURATED_CAPITOLI`) is an editorial choice
re-confirmed per edition, not inferred at runtime.

```sh
docker compose cp services/prezzari-service/db/ingest_prezzario.py \
    prezzari-service:/tmp/ingest_prezzario.py
docker compose cp prezzario-2026.csv prezzari-service:/tmp/prezzario-2026.csv
docker compose exec prezzari-service \
    python /tmp/ingest_prezzario.py /tmp/prezzario-2026.csv --publication 2026
```

**`omi_locazione`** (Lista A) — one row per comune × Zona OMI × tipologia ×
stato: `region_id` (the monolith region the comune maps to, referenced **by
id only** — no FK, shared DB per ADR-0001 — and indexed for
`WHERE region_id = :region_id`), `zona`/`tipologia`/`stato`,
`canone_min`/`canone_max`/`um` (€/m²/mese), `publication` (semestral edition
stamp, e.g. `2025 · II semestre`). Same static, latest-only lifecycle via
`ingest_omi.py`; the load-bearing parse + Campania/locazione filtering lives
in the tested pure module `src/routers/prezzari/omi_parser.py` (`parse_omi` /
`CAMPANIA_PROVINCE`). The CLI adds the one thing the pure parser can't do:
map each OMI comune's **ISTAT code** to its monolith `region_id` (via
`areas.metadata->>'ref:ISTAT'` on the comune boundaries, `area_type_id = 3`);
rows whose ISTAT doesn't resolve to a Campania region are skipped. The
Campania province set (`CAMPANIA_PROVINCE`) is likewise editorial.

```sh
docker compose cp services/prezzari-service/db/ingest_omi.py \
    prezzari-service:/tmp/ingest_omi.py
docker compose cp omi-2025-s2.csv prezzari-service:/tmp/omi-2025-s2.csv
docker compose exec prezzari-service \
    python /tmp/ingest_omi.py /tmp/omi-2025-s2.csv --publication "2025 · II semestre"
```

## Links out

- [Decision records](adr/)
- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
