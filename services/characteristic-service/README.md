# Characteristic Widget Service (PRAIM)

A standalone FastAPI deployable: a **write** Widget that attaches a Bene's
Blueprints (planimetrie) and Scheda (reuse data) to a POI. It shares the Janus
monolith's Supabase database but is a **separate deployable** and **never
modifies the monolith's code** (see `../../docs/adr/0001-shared-database.md`).
Monolith conventions are mirrored by copying, not importing.

This repo is the walking skeleton (task 01): `/health`, the unguarded UI bundle
route `/characteristic/widget.js`, and a guarded reachability `ping`. The guard
is **authentication-only** in v1 (`require_scopes([])` — any valid JWT, no
scope); the Workshop Master gate (write scope + per-POI ownership) slots in later
at that single seam. The `building_*` tables and real read/write routes arrive in
later slices.

> Note: this service carries **no CORS**. The
> [edge gateway](../../docs/adr/0002-edge-gateway-single-front-door.md) fronts it
> same-origin, so the browser never calls it directly and it is not
> browser-facing — "Widget services carry no CORS" is the standing pattern.

## Blueprint image processing (finalised caps)

Every uploaded Blueprint passes through a server-side image-processor
(`src/imaging/blueprint_processor.py`) before it is stored, so plans stay
**bounded** and **legible**:

- **Longest-edge cap — 2400px** (`MAX_BLUEPRINT_DIMENSION`). Oversized plans are
  downscaled to this; phone-photo resolution is trimmed while dense drawings stay
  readable.
- **Finalised byte cap — 5 MiB** (`FINALISED_BLUEPRINT_BYTES`). The processor keeps
  shrinking until the re-encoded bytes fit, so a stored Blueprint *always* respects
  the cap (it is never rejected for size).
- **Input cap — 10 MiB** (`MAX_BLUEPRINT_BYTES`). A cheap pre-decode guard that
  rejects an over-large body before it is decoded.
- **Resampling — LANCZOS**: the documented choice that preserves the thin black
  lines of engineering drawings instead of blurring them away.
- **Format validation is decode-based**: the bytes must actually open as PNG / JPEG
  / WebP; the declared `content_type` is only a cheap pre-filter.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
make ui                           # build the <characteristic-widget> bundle once
make run                          # or: uvicorn src.app:app --port 28002 --reload
```

- Health: `GET http://localhost:28002/health` → `{"status": "ok"}`
- Ping:   `GET http://localhost:28002/characteristic/ping` → 200 with a valid JWT, 401 without
- Docs:   `GET http://localhost:28002/docs`

## Test

```bash
pip install -r requirements-dev.txt
make test                          # or: python -m pytest
```

## Docker

```bash
make build                         # docker build -t praim/characteristic-service .
make dev                           # docker compose -f docker-compose.dev.yml up --build
```

The dev port is `28002` (the monolith uses `28000`, the demographic widget `28001`).
