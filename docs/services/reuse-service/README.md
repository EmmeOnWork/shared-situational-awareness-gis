# Workshop Selector

**What it is** — `reuse-service` is a full-stack Widget microservice in the Janus
strangler-fig stack, mounted under the `/reuse` prefix. It owns the
`building_workshop` registry — the canonical list of Bene (reuse-POIs) — and
publishes the **Active Workshop** that other, "sensitive" widgets react to.

**When to read it** — when you're building or touching this widget, or any other
sensitive widget (starting with `characteristic-service`) that needs to know the
Active Workshop.

## How it works

**Data owned.** The service owns `public.building_workshop` in the shared
Supabase database:

```sql
CREATE TABLE IF NOT EXISTS public.building_workshop (
    poi_id     bigint PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now()
);
```

`poi_id` references the monolith's `pois` table **by value only** — no
cross-domain foreign key, so this service's migrations stay decoupled from the
monolith's (ADR-0001). A `master_user_id` ("Workshop Master") is anticipated but
not modelled yet. The table is ensured best-effort on boot (never fatal; logged
and skipped if the DB role can't write) and mirrored for operators in
`catalog/registry.sql`. Bene are designated by inserting `poi_id` values — v1
seeds them directly by SQL (`catalog/seed-benes.sql`); there is no admin
curation UI.

**Routes** (mounted at `/reuse`; no CORS — the edge gateway fronts it
same-origin, so the browser never calls it directly):

- `GET /health` → `{"status": "ok"}` — liveness.
- `GET /reuse/benes` → `[{poiId, name, lat, lng}, …]` — **JWT-guarded**
  (`reuse:read` scope, enforced as a router-level dependency). Built from
  `building_workshop` LEFT JOIN `pois` on `poi_id`, ordered by name (nulls
  last); `lat`/`lng` come from `ST_Y(geom)`/`ST_X(geom)`. A Bene whose POI row
  can't be resolved (null name/coords) is omitted — it can't be named, panned
  to, or published. Returns `[]` on an empty registry.
- `GET /reuse/widget.js` → the built `<reuse-widget>` bundle, **unguarded** (a
  `<script>` load carries no bearer token — the data route above stays behind
  the scope instead). Responds 503 with a build hint if `make ui` hasn't run
  yet. Served with `Cache-Control: no-cache` so a redeploy is never masked by a
  stale cached bundle.

**Frontend.** `<reuse-widget>` is a dependency-free custom element (Web
Component) shipped by this same service. It reads `token`/`base` attributes
from its host page, fetches `/reuse/benes` with a bearer token, and renders a
dropdown whose menu is a native top-layer popover (so it isn't clipped by the
dashboard card or affected by the grid item's transform). Picking a row:

1. Publishes the pick as the **Active Workshop**: `publishActiveWorkshop()`
   sets a retained `window.__praimActiveWorkshop` and dispatches a
   `praim:workshop-selected` `CustomEvent` on `window` with
   `detail: {poiId, lat, lng, name}` (ADR-0003). The retained value lets
   late-mounting/HMR'd widgets converge at mount; the event lets
   already-subscribed ones react immediately. This is the dedicated Workshop
   channel — ADR-0005 later generalized the pattern into a multi-axis
   `praim:selection:<axis>` / `window.__praimSelections` bus for other
   selectors, but the Workshop axis itself still runs on this original
   contract.
2. Reflects the `poiId` into the page URL's `poiId` query param via
   `history.replaceState` (refines the current URL, no navigation), so a
   dashboard's URL is bookmarkable/shareable.

On load, the widget restores selection from that `poiId` param (resolved
against the fetched Bene list) by re-publishing through the same path, so
already-mounted sensitive widgets converge and late joiners still read the
retained value; a stale or unresolvable `poiId` degrades cleanly (no event, no
false selection).

Widgets that consume the Active Workshop depend only on this bus contract,
never on the Selector itself. Panning the GIS map to the selected Bene is
likewise not this service's own code: the host page installs one generic
listener (`useWorkshopMapPan`) that reacts to the same event (ADR-0004) —
reuse-service only ever publishes.

**Catalog self-registration.** On boot, the service best-effort upserts one row
into the shared `dashboards_config.widget_types` (`type = "reuse"`), pointing
`default_props.additionalConfig.remote` at
`{src: "/reuse/widget.js", tag: "reuse-widget"}` — the fragment the monolith's
generic `RemoteWidget` seam uses to mount the bundle from a hand-curated
dashboard, with no monolith code change. Registration is idempotent
(`ON CONFLICT (type) DO UPDATE SET default_props`) and toggled by
`REGISTER_IN_CATALOG`; `catalog/widget-type.sql` is the manual fallback.

## Running it

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
make ui                           # build the <reuse-widget> bundle (serves /reuse/widget.js)
make run                          # or: uvicorn src.app:app --port 28002 --reload
```

- Health: `GET http://localhost:28002/health`; docs: `GET http://localhost:28002/docs`.
- Test: `pip install -r requirements-dev.txt && make test` (or `python -m pytest`).
- Docker: `make build` (`docker build -t praim/reuse-service .`) or `make dev`
  (`docker compose -f docker-compose.dev.yml up --build`). The Dockerfile is
  two-stage — a `node:20-slim` stage runs the UI's `npm run build`, a
  `python:3.12-slim` stage runs FastAPI and copies the built bundle to
  `src/static/reuse-widget.js` — and drops to a non-root user. Dev port is
  `28002` (the monolith uses `28000`, demographic `28001`).
- Settings (env / `.env`): `JWT_ALGORITHM` (default `RS256`),
  `JWT_VERIFICATION_KEY`, `DATABASE_URL` (the same shared Supabase the monolith
  reads), `REGISTER_IN_CATALOG` (default `true`).

**Operator data steps.** The registry, its seed rows, and the catalog row are
data, not service code (ADR-0001), applied against the shared database:

- `catalog/registry.sql` — create `building_workshop` (also best-effort
  ensured on boot).
- `catalog/seed-benes.sql` — designate which POIs are Bene, by `poi_id` (v1:
  direct insert, no admin UI).
- `catalog/widget-type.sql` — register the widget row in
  `dashboards_config.widget_types` (also best-effort upserted on boot).
- Granting the `reuse:read` scope itself needs a role grant an operator runs
  once — see [operator-sql.md](operator-sql.md).

## Links out

- [ADR-0003 — Active Workshop selection bus](../../adr/0003-active-workshop-selection-bus.md)
- [ADR-0004 — Host pans the map on the Active Workshop bus](../../adr/0004-host-pans-map-on-active-workshop.md)
- [ADR-0005 — Generalized selection bus](../../adr/0005-generalize-selection-bus.md)
- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
