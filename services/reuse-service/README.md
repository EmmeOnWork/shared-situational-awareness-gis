# Reuse Widget Service — Workshop Selector (PRAIM)

A standalone full-stack Widget that shows a low-noise **toggle-list of the Bene**
(reuse-POIs) and — in later slices — pans the GIS map to the chosen one and
publishes the **Active Workshop** on a shared-`window` event bus (ADR-0003) that
sensitive widgets react to. It shares the Janus monolith's Supabase database but
is a **separate deployable** and **never modifies the monolith's code**
(`../../docs/adr/0001-shared-database.md`). Monolith conventions are mirrored by
copying, not importing — it reuses the proven demographic seam.

This service is built **first**: it **owns** the `building_workshop` registry
(the canonical list of Bene, keyed by `poi_id`, in `public`), so the
`characteristic-service` has a real source to consume.

This repo is **Slice 1** (task 01): the `building_workshop` registry, the
JWT-guarded `GET /reuse/benes` list joined to the monolith's `pois`, the
unguarded `GET /reuse/widget.js` bundle, catalog self-registration, and a
**read-only** `<reuse-widget>` toggle-list. Selection (pan + Active Workshop
bus) and URL persistence arrive in Slices 2–4.

> Note: this service carries **no CORS**. The
> [edge gateway](../../docs/adr/0002-edge-gateway-single-front-door.md) fronts it
> same-origin, so the browser never calls it directly — "Widget services carry no
> CORS" is the standing pattern.

## Endpoints

- `GET /health` → `{"status": "ok"}` (liveness)
- `GET /reuse/benes` → `[{poiId, name, lat, lng}, …]` — **JWT-guarded**
  (`reuse:read`). Each Bene from `building_workshop` joined to its POI for name +
  coords; `[]` on an empty registry; a Bene whose POI is missing is omitted.
- `GET /reuse/widget.js` → the `<reuse-widget>` bundle, **unguarded** (503 with a
  build hint until `make ui` builds it).

## Operator data steps

The Selector needs data wired in the **shared** DB (none of it is service code):

- [`docs/operator-sql.md`](docs/operator-sql.md) — grant the `reuse:read` scope.
- [`catalog/registry.sql`](catalog/registry.sql) — create `building_workshop`.
- [`catalog/seed-benes.sql`](catalog/seed-benes.sql) — designate Bene by `poi_id`.
- [`catalog/widget-type.sql`](catalog/widget-type.sql) — register in "Add widget".

The registry and the catalog row are also **best-effort ensured/upserted on
boot**; the SQL is for environments where the service's DB role may not write.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
make ui                           # build the <reuse-widget> bundle (serves /reuse/widget.js)
make run                          # or: uvicorn src.app:app --port 28002 --reload
```

- Health: `GET http://localhost:28002/health` → `{"status": "ok"}`
- Docs:   `GET http://localhost:28002/docs`

## Test

```bash
pip install -r requirements-dev.txt
make test                          # or: python -m pytest
```

## Docker

```bash
make build                         # docker build -t praim/reuse-service .
make dev                           # docker compose -f docker-compose.dev.yml up --build
```

The dev port is `28002` (the monolith uses `28000`, demographic `28001`).
