# Vocazione Selector

**What it is** — `vocazione-service` is a standalone, read-only /
stores-nothing selector Widget (URL prefix `/vocazione`): a dropdown of the 16
fixed Vocazioni that publishes the Active Vocazione page-globally. It owns no
tables and no data route — client-only, it serves only its bundle.

**When to read it** — when you're building or touching this widget, or
consuming the Active Vocazione elsewhere.

## How it works

A **Vocazione** is one of the **16 fixed archetypes** from
*Elenco_Funzioni.pdf* (e.g. *Dimora del Benessere*, *Atelier di Ricordi*) — a
target reuse function a building could be repurposed into. It is a closed
catalog, not free text: each entry is a stable kebab-slug `id` plus an Italian
`label`, shipped inside the UI bundle as a frontend constant (`VOCAZIONI`) —
never stored against any building.

Picking one publishes it as the **Active Vocazione** — the single page-global
filter lens, or `null` for "Tutte le vocazioni" (show everything) — on the
generalized selection bus
([ADR-0005](../../adr/0005-generalize-selection-bus.md)). The resulting
contract: a per-axis event `praim:selection:vocazione` plus a retained
`window.__praimSelections.vocazione`, behind copied
`publishSelection`/`subscribeSelection`/`readSelection` helpers (no shared
package — each deployable keeps its own copy, per the strangler pattern). The
chosen slug is also reflected into a `?vocazione=<slug>` URL param (removed
entirely on clear) and restored from it at mount, so a focused dashboard is
bookmarkable/shareable.

The Active Vocazione is a **second, independent axis** alongside the **Active
Workshop** (which Bene is under consideration, published by the Workshop
Selector in [reuse-service](../reuse-service/README.md)) — a dashboard can
have both selected at once, and neither drives the other.

The widget owns nothing: no table, no data route of its own — its only output
is the browser event above. There is deliberately no stored
building→Vocazione link, so a future map layer filtering buildings by the
selected Vocazione has no data to query yet; this widget only guarantees the
broadcast such a consumer could react to.

## Running it

Full-stack Widget: a Node stage builds the `<vocazione-widget>` custom
element bundle; a Python/FastAPI stage serves it plus `/health`.

- **Backend** — Python 3.12, FastAPI (`fastapi[standard]`,
  `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy`,
  `psycopg[binary]`). Install with `pip install -r requirements.txt`
  (`requirements-dev.txt` adds `pytest`/`httpx`). Run with `uvicorn
  src.app:app --host 0.0.0.0 --port 28003 --reload` (or `make run`); test with
  `python -m pytest` (or `make test` — `pytest.ini` sets `testpaths = tests`).
  Tests are hermetic: the catalog-registration lifespan hook never fires
  under a plain `TestClient`, so no test touches a database.
- **UI** — Node 20, plain esbuild, no framework. From `ui/`: `npm install`,
  `npm run build` (bundles `src/vocazione-widget.ts` →
  `dist/vocazione-widget.js`), `npm run typecheck`, `npm test` (`node --test
  "src/**/*.test.ts"`). `make ui` builds it and copies the output to
  `src/static/` so FastAPI can serve `/vocazione/widget.js` locally.
- **Docker** — `make build` (or `docker build -t praim/vocazione-service .`)
  runs both stages into one image; default port **28003** (monolith 28000,
  demographic 28001, characteristic/reuse 28002).
- **Env vars** — `DATABASE_URL` (the shared Supabase, used solely by the
  best-effort catalog self-registration upsert into
  `dashboards_config.widget_types`); `REGISTER_IN_CATALOG` (bool, default
  `true` — set `false` to skip it and apply `catalog/widget-type.sql` manually
  instead).

## Links out
- [ADR-0005 — Generalize the selection bus](../../adr/0005-generalize-selection-bus.md)
- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
