# Demographic Widget Service (PRAIM)

A standalone FastAPI deployable that serves aggregated ISTAT demographic data as a
dashboard data-source. It shares the Janus monolith's Supabase database but is a
**separate deployable** and **never modifies the monolith's code** (see
`../docs/adr/0001-shared-database.md`). Monolith conventions are mirrored by
copying, not importing.

This repo is the walking skeleton (task 01): a `/health` endpoint, CORS, and
OpenAPI docs. Auth and database access arrive in later slices.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
make run                          # or: uvicorn src.app:app --port 28001 --reload
```

- Health: `GET http://localhost:28001/health` → `{"status": "ok"}`
- Docs:   `GET http://localhost:28001/docs`

## Test

```bash
pip install -r requirements-dev.txt
make test                          # or: python -m pytest
```

## Docker

```bash
make build                         # docker build -t praim/demographic-service .
make dev                           # docker compose -f docker-compose.dev.yml up --build
```

The dev port is `28001` (the monolith uses `28000`).
