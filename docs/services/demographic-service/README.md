# Demographic

**What it is** — A read-only FastAPI Widget (prefix `/demographics`) that serves
aggregated ISTAT demographic data as a dashboard data-source, reading two tables
it owns (`public.demographic`, `public.demographic_boundary`) plus its own UI
bundle. It shares the Janus monolith's Supabase database but is a separate
deployable that never modifies the monolith's code
([ADR-0001](../../adr/0001-shared-database.md)).

**When to read it** — when you're building or touching this widget.

## How it works

### Domain

Monolith conventions (naming, contracts) are mirrored by copying, not
importing.

- **Territory** — a named administrative unit demographic data is reported for,
  with a **level**: `province` (106) ⊂ `region` (20) ⊂ `macro_area` (5) ⊂
  `national` (1). The join key is the Territory **name** — the canonical full
  official Italian form (e.g. `Friuli-Venezia Giulia`), with the raw ISTAT label
  (e.g. `Friuli-V. G.`) retained alongside for traceability. ISTAT publishes
  pre-aggregated values at every level; the service never rolls one level up
  into another. ("Territory" replaces the vaguer "country", which stays
  reserved for nations.)
- **Demographic profile** — the full set of indicators for one Territory,
  assembled by integrating ISTAT Tables 1 and 4 on the Territory name:
  - **Population by citizenship** — resident headcount split
    Italian/foreign/total, in **thousands**. A *stock* (not "immigrants" — that
    conflates stock with flow).
  - **Age structure** — resident share (%) in `0–14`, `15–64`, `65+`.
  - **Migration rate** — net moves per 1,000 residents/year, internal, foreign
    and total. A *flow*, distinct from the foreign population stock — never
    merge the two under "immigration".
- **Selection layer & estimates** — the (not-yet-built) map feature that
  resolves a finer clicked shape to the nearest Territory that has data, and
  labels the result an **estimate** (e.g. a click on comune `Monteverde`, which
  has no ISTAT row, resolves to province `Avellino`; the response then carries
  `level: province` / `territory_name: Avellino` so the caller can label it a
  province-level estimate). The demographic service does no such resolution
  itself: asking `/raw` for a name it doesn't have is a 404, not a fallback.
  Only intensive indicators (age shares, migration rates) can be honestly
  inherited by a finer unit this way; absolute population counts cannot.
- **Widget** — a backend data-source domain returning the data a dashboard
  panel renders, server-side only; this is one, alongside `pollution` and
  `weather` in the monolith.
- **DataResponse** — the canonical response contract reused from the monolith:
  a `label`, a `data` map of key→value, an optional datetime range (always null
  here — demographics aren't a time series), and `metadata`. This widget puts
  the nine indicators in `data` and context (level, units, reference periods,
  quality flags, answered Territory) in `metadata`.
- **Region / Area / Area Type** — the monolith's own geography tables.
  Referenced by **name** only, never by geometry; a future
  `territory_name → regions` foreign key is anticipated but not built.

### Routes & contract

All routes below are under `/demographics/*` except `/health`, and all are
guarded at router-include level by the `demographics:read` scope (`src/app.py`)
except `widget.js` and `/health`. Widget services carry no CORS: the
[edge gateway](../../edge-gateway/README.md) fronts every widget same-origin,
so the browser never calls this service directly.

| Route | Behavior |
| --- | --- |
| `GET /health` | Liveness probe → `{"status": "ok"}`. |
| `GET /demographics/raw?territory=` | Look up one Territory by exact name in `public.demographic`. 404 if not found. |
| `GET /demographics/at-point?lat=&lng=` | Resolve a click by geometry: `ST_Contains` over `public.demographic_boundary` joined to `public.demographic` on `territory_name`. Falls back to the `national` row if no province contains the point; `503` if `demographic_boundary` is empty (not seeded yet). |
| `GET /demographics/territories` | Discovery list of every valid `{name, level}`, ordered province → region → macro_area → national, then name. |
| `GET /demographics/ping` | DB-free reachability probe behind the same guard; used by the auth test suite and as the gateway smoke check. |
| `GET /demographics/widget.js` | Unguarded; serves the built UI bundle from `src/static/`, or `503` if it hasn't been built yet. |

### Data

- `public.demographic` — one wide row per Territory, name-keyed
  (`territory_name` is unique across all four scales and is the primary key the
  router looks up by); 9 indicator columns: `pop_total`, `pop_italian`,
  `pop_foreign`, `age_share_0_14`, `age_share_15_64`, `age_share_65_plus`,
  `mig_rate_internal`, `mig_rate_foreign`, `mig_rate_total`. No geometry, no
  time series — unlike `pollution`, which is normalized because it carries
  both.
- `public.demographic_boundary` — one polygon per province, FK-referencing
  `demographic.territory_name`; backs `/at-point`.
- The service never issues DDL (schema arrives via infrastructure) and never
  seeds data (loaded manually) — see "Loading data" under Running it.

### Auth

The service verifies JWTs but holds **no signing key** — it never issues
tokens (one identity system, the monolith's). It mirrors the monolith's env var
names (`JWT_ALGORITHM`, `JWT_VERIFICATION_KEY`) so the same deployment config
works. Enforcement is scope-based (`demographics:read`); granting that scope to
a role is an operator data step the service never performs itself — see
"Enabling `demographics:read`" under Running it.

## Running it

### Local

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
make run                          # or: uvicorn src.app:app --port 28001 --reload
```

- Health: `GET http://localhost:28001/health` → `{"status": "ok"}`
- Docs: `GET http://localhost:28001/docs`
- Dev port `28001` (the monolith uses `28000`).

### Test

```bash
pip install -r requirements-dev.txt
make test                          # or: python -m pytest
```

### Docker

```bash
make build                         # docker build -t praim/demographic-service .
make dev                           # docker compose -f docker-compose.dev.yml up --build
```

Two-stage `Dockerfile`: a `node:20-slim` stage builds the UI bundle, then a
`python:3.12-slim` stage installs `requirements.txt` (the leaner runtime
manifest — local dev/test uses `requirements-dev.txt` instead), copies `src/`
plus the built bundle into `src/static/`, runs as a non-root `app` user, and
exposes port `28001`.

### Environment variables

| Var | Default | Meaning |
| --- | --- | --- |
| `JWT_ALGORITHM` | `RS256` | Mirrors the monolith's env var name; used for verification only. |
| `JWT_VERIFICATION_KEY` | empty | Public key used to verify the monolith's tokens. |
| `DATABASE_URL` | empty | Same Supabase database the monolith reads. |
| `REGISTER_IN_CATALOG` | `true` | Toggles catalog self-registration (below). |

### Catalog self-registration

On startup (FastAPI `lifespan`), the service best-effort upserts its own row
into the shared `dashboards_config.widget_types` table (creating the
schema/table first if missing) — `type = 'demographic'`, pointing
`default_props.additionalConfig.remote` at `src: /demographics/widget.js`,
`tag: demographic-widget` — so a hand-curated dashboard can reference it with
no monolith code change. Failure (table missing, DB role lacks rights) is
logged and swallowed, never fatal. Disable with `REGISTER_IN_CATALOG=false` and
apply `catalog/widget-type.sql` manually instead (the same upsert, kept in
sync).

### Loading data (`db/`)

`public.demographic`'s and `public.demographic_boundary`'s **schema** comes up
automatically: `db/demographic-schema.sql` runs on every bring-up via the root
compose's one-shot `demographic-schema-init` service (`CREATE TABLE IF NOT
EXISTS`, idempotent). **Data** is manual, once per database:

```bash
docker compose exec -T ju-postgres \
  psql -U janus -d janus -v ON_ERROR_STOP=1 \
  -c "\copy public.demographic FROM STDIN WITH (FORMAT csv, HEADER true)" \
  < data/demographic.csv
```

The CSV column order matches the table. Re-running appends rather than
replacing; `TRUNCATE public.demographic;` first to reload (or script an
`INSERT ... ON CONFLICT`).

Province boundaries (for `/at-point`) load the same way, from an ISTAT
province boundary GeoJSON (EPSG:4326, e.g. "Confini delle unità
amministrative — Province/UTS"):

```bash
docker compose cp services/demographic-service/db/load_boundaries.py \
    demographic-service:/tmp/load_boundaries.py
docker compose cp provinces.geojson demographic-service:/tmp/provinces.geojson
docker compose exec demographic-service \
    python /tmp/load_boundaries.py /tmp/provinces.geojson --name-field DEN_UTS
```

`load_boundaries.py` reconciles each polygon's name to the exact
`territory_name` already in `public.demographic`, applying an `OVERRIDES` map
for ISTAT spellings that differ (e.g. `Bolzano/Bozen` → `Bolzano-Bozen`);
unmatched polygons print at the end so they can be added there. The load
upserts by `territory_name`, so it's idempotent. Until it runs,
`/demographics/at-point` answers `503` and the widget falls back to its manual
dropdown.

### Enabling `demographics:read` (operator SQL)

A data step, not service code: the service only verifies and enforces the
scope, it never writes `scopes` or `role_scopes`. Run once against the shared
Supabase Postgres:

```sql
INSERT INTO public.scopes (name, description)
VALUES ('demographics:read', 'Read aggregated ISTAT demographic data')
ON CONFLICT (name) DO NOTHING;

INSERT INTO public.role_scopes (role_id, scope_id)
SELECT r.id, s.id
FROM public.roles r
CROSS JOIN public.scopes s
WHERE upper(r.name) = 'VIEWER'
  AND s.name = 'demographics:read'
ON CONFLICT DO NOTHING;
```

Adjust the role name(s) to your deployment. No service restart is required —
the scope is read from each token. Column names (`scopes.description`, the
`role_scopes` PK) follow the monolith's shared schema; only the conflict
targets are guaranteed environment-independent.

### UI build

The frontend half is a framework-free custom element `<demographic-widget>` —
nothing here depends on the monolith, so it runs in any HTML page. Host
contract:

| Attribute | Set by | Meaning |
| --- | --- | --- |
| `token` | host | monolith-issued JWT, refreshed by the host on login/expiry |
| `base` | host | edge-gateway origin (`""` = same origin) |

```bash
npm install
npm run build      # → dist/demographic-widget.js
```

`make ui` (from the service root) runs this and copies the bundle into
`src/static/` for FastAPI to serve at `/demographics/widget.js`; the
production image builds it in the Dockerfile's Node stage; `dist/` is
git-ignored.

## Links out

- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
