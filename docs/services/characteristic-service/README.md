# Building Characteristic

**What it is** — A standalone FastAPI Widget in the Janus strangler-fig stack,
under URL prefix `/characteristic`. It lets a Workshop Master attach a Bene's
Blueprints (planimetrie) and Scheda (reuse data) to a POI clicked on the map.
Unlike the read-only Widgets it is a **write** Widget (binary Blueprint upload +
authorized mutations), and it is a **sensitive** widget that reacts to whichever
Bene is the Active Workshop.

**When to read it** — when you're building or touching this widget.

## How it works

### Domain

- **Workshop** — the unit of work around reusing one confiscated/public **Bene**:
  ties one **POI** to the Blueprints + Scheda that describe its reuse. Exactly
  one Workshop per Bene/POI. The registry table `building_workshop(poi_id,
  created_at)` is the canonical list of Bene the Selector reads — a Bene exists
  in it even before it has a Scheda or Blueprints. (Avoid "project"/"site" — vaguer,
  overloaded.)
- **Workshop Master** — the single user meant to own one Workshop: the only one
  allowed to upload Blueprints / edit the Scheda, and only for **their own** POI,
  not globally. Not an "admin" (global) — a Master is bound to one Bene.
- **Bene** — the real-world asset a Workshop is about: a **special POI** (one
  *adibito al riuso*), not an ordinary map POI. A POI becomes a Bene by having a
  Workshop. Referenced by POI `id` only — the service never owns geometry;
  comune/coordinate are read from the POI and never re-stored. The Scheda owns
  only what the POI lacks (denominazione edificio, estremi catastali) plus all
  reuse data.
- **Scheda** (Scheda di Individuazione Immobile) — the structured reuse data for
  one Bene, exactly one per Workshop/POI: the standardised *Provincia di
  Avellino* form (identification, tipologia/destinazione d'uso, titolo di
  proprietà/disponibilità, stato d'uso e condizioni, vincoli, documentazione
  disponibile, referente tecnico comunale), stored as **fields**, not an opaque
  PDF. Created and edited through the widget's Load form: the **first** Load
  creates it, **later** Loads present it pre-filled and editable. All fields are
  optional/non-blocking — a Blueprint can be saved with the Scheda left empty.
  An older Cassano-style sheet (Consistenza, Estremi Catastali) maps its
  extra/renamed fields into this canonical schema.
- **Blueprint** — one uploaded image of a black-and-white engineering drawing
  (planimetria) attached to a Bene, one per **Sezione** (floor or
  cross-section); unique per `(Bene, Sezione)`. Stored as `bytea`, served via
  `GET /characteristic/blueprints/{id}`. Avoid "photo" (too generic).
- **Sezione** — the floor or vertical cross-section a Blueprint depicts (e.g.
  *piano terra*, *2° piano*, *sezione A-A*). The toggle list in the UI is
  exactly the set of Sezioni a Bene has.

### Why building data isn't stored on the POI

Building data lives in this service's own `building_workshop` / `building_scheda`
/ `building_blueprint` tables in `public`, referencing `public.pois(id)` **by id
only** — never written, no column added, no `metadata` reuse, no cross-domain
FK. See the [decision record](adr/0001-building-data-not-in-pois.md) for why.

### Active Workshop (sensitive widget)

This widget is **sensitive**: it shows the Scheda + Blueprints of whichever Bene
is the **Active Workshop** — established by the separate Workshop Selector
widget — and sits idle when none is selected. Transport: a browser-level event
bus (a `praim:workshop-selected` CustomEvent plus a retained last value,
`window.__praimActiveWorkshop`, read at mount to survive late-join/HMR). The
widget depends only on the contract (an Active Workshop `poiId`), never on the
Selector's implementation. Persisting the Active Workshop across reload and
moving the GIS map are the Selector's/host's responsibility, not this widget's.

### Routes

- `GET /health` and the unguarded UI bundle route `GET /characteristic/widget.js`
- `GET /characteristic/workshops/{poi_id}` — a Bene's Scheda + Blueprints
- `PUT /characteristic/scheda/{poi_id}`
- `POST` / `GET` / `DELETE /characteristic/blueprints[/{blueprint_id}]`
- `GET /characteristic/ping` — guarded reachability check

### Auth (v1 — roles deferred)

The guard is **authentication-only** (`require_scopes([])` — any valid JWT, no
scope): write routes require login, reusing the copied `get_current_user`; the
bundle stays unguarded. There is no `building:write` scope, no per-POI ownership
check, and no DB role yet — kept authenticated rather than open specifically to
avoid an unguarded binary-upload endpoint. A future Workshop Master gate (write
scope + per-POI ownership) slots in later at that single seam (the route's
dependency). Anticipated, not built: roles arrive together with a richer access
model where a dashboard is created by a Master or admin who invites other users
under a different (read-only) role — this may eventually refine Workshop into
"a dashboard + its participants around one Bene."

### Blueprint image processing (finalised caps)

Every uploaded Blueprint passes through a server-side image processor
(`src/imaging/blueprint_processor.py`) before it is stored:

- **Longest-edge cap — 2400px** (`MAX_BLUEPRINT_DIMENSION`). Oversized plans are
  downscaled to this.
- **Finalised byte cap — 5 MiB** (`FINALISED_BLUEPRINT_BYTES`). The processor
  keeps shrinking until the re-encoded bytes fit, so a stored Blueprint always
  respects the cap and is never rejected for size.
- **Input cap — 10 MiB** (`MAX_BLUEPRINT_BYTES`). A cheap pre-decode guard that
  rejects an over-large body before it is decoded.
- **Resampling — LANCZOS**: preserves the thin black lines of engineering
  drawings instead of blurring them away.
- **Format validation is decode-based**: the bytes must actually open as PNG /
  JPEG / WebP; the declared `content_type` is only a cheap pre-filter.

### Shared database & no CORS

Shares the Janus monolith's Supabase database as a separate deployable and never
modifies the monolith's code (monolith conventions are mirrored by copying, not
importing) — see [ADR-0001, shared database](../../adr/0001-shared-database.md).
Carries **no CORS**: the [edge gateway](../../edge-gateway/README.md) fronts it
same-origin, so the browser never calls it directly — the standing pattern for
all Widget services (see [ADR-0002](../../adr/0002-edge-gateway-single-front-door.md)).

## Running it

### Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
make ui                           # build the <characteristic-widget> bundle once
make run                          # or: uvicorn src.app:app --port 28002 --reload
```

- Health: `GET http://localhost:28002/health` → `{"status": "ok"}`
- Ping: `GET http://localhost:28002/characteristic/ping` → 200 with a valid JWT, 401 without
- Docs: `GET http://localhost:28002/docs`

### Test

```bash
pip install -r requirements-dev.txt
make test                          # or: python -m pytest
```

### Docker

```bash
make build                         # docker build -t praim/characteristic-service .
make dev                           # docker compose -f docker-compose.dev.yml up --build
```

The dev port is `28002` (the monolith uses `28000`, the demographic widget `28001`).

### Database (`db/`)

`characteristic-schema.sql` is the schema-only DDL (plus DML grants) for the
`building_*` tables, applied by the compose `characteristic-schema-init`
one-shot on every bring-up — **not** by the service at runtime, so the service
only ever issues DML, never DDL. It creates three tables:

- `building_workshop(poi_id, created_at)` — the Bene registry (owned by
  reuse-service; this service reads it, fallback-upserts on first write).
- `building_scheda(poi_id → building_workshop, …)` — one Scheda per Bene.
- `building_blueprint(id, poi_id → building_workshop, sezione, image bytea, …,
  UNIQUE(poi_id, sezione))` — N per Bene, one per Sezione.

The script grants the service's DB role `INSERT`/`UPDATE`/`DELETE` on those
tables (and `USAGE` on the blueprint id sequence); the role defaults to the
local `janus`, and the compose one-shot passes the real one via `-v
service_role=...`. `poi_id` references `public.pois(id)` by id only — no
cross-domain FK into the monolith (FKs *among* the `building_*` tables are
intra-domain and fine). Idempotent: re-running it on an existing database is a
no-op (`CREATE TABLE IF NOT EXISTS`; grants are re-asserted).

### UI (`ui/`)

The frontend half is a single, framework-free custom element
`<characteristic-widget>`, served at `/characteristic/widget.js` and mounted by
the monolith's generic `RemoteWidget` seam; nothing here depends on the
monolith — the element runs in any HTML page. It mounts in Shadow DOM and calls
only `/characteristic/*` on its own service, through the gateway, with the
host's JWT.

Host contract:

| Attribute | Set by   | Meaning                                                     |
| --------- | -------- | ------------------------------------------------------------ |
| `token`   | the host | monolith-issued JWT; refreshed by the host on login/expiry    |
| `base`    | the host | edge-gateway origin (`""` = same origin)                      |

Build:

```bash
npm install
npm run build      # → dist/characteristic-widget.js
```

`make ui` (from the service root) runs this and copies the bundle into
`src/static/` where FastAPI serves it. The production image builds it in a Node
stage (see the service `Dockerfile`); `dist/` is git-ignored.

## Links out

- [Decision records](adr/)
- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
