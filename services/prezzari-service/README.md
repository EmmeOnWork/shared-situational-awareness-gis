# prezzari-service — I Prezziari Widget

A read-only full-stack Widget (gateway prefix `/prezzari`, element `<prezzari-widget>`)
that shows **two reference price lists side by side** to support reasoning about the
economic pre-feasibility of reusing a building:

- **Left — Prezziario di Locazione (OMI):** the rental quotations of the **clicked comune**
  (comune-scoped; updates on click).
- **Right — Prezzario dei Lavori:** a curated slice of the **Regione Campania** public-works
  price list (region-fixed; renders on mount, unchanged by a click).

It reads its **own snapshot tables** (later slices), never calls the source sites at runtime
(prezzari ADR-0001), computes nothing and merges nothing, and never edits the monolith. See
[CONTEXT.md](./CONTEXT.md) and [the PRD](../../.scratch/prezzari/PRD.md).

## Layout

- `src/app.py` — FastAPI: `/health`, the unguarded `/prezzari/widget.js` bundle
  (`Cache-Control: no-cache`), and the two JWT-guarded data routes.
- `src/routers/prezzari/prezzari_router.py` — `GET /prezzari/locazione?lat&lng` (Lista A) and
  `GET /prezzari/lavori?capitolo?&q?` (Lista B). **Currently stubbed** (tracer slice 01).
- `src/security/`, `src/config/` — copied JWT verify + shared-DB helper + Settings +
  best-effort catalog self-registration (`type='prezzari'`).
- `ui/` — the `<prezzari-widget>` custom element (two-column layout), built to
  `src/static/prezzari-widget.js` and served by the app.
- `catalog/widget-type.sql` — manual catalog registration fallback.

## Develop

```sh
make ui        # build the <prezzari-widget> bundle into src/static/
make run       # uvicorn on :28008 (through the gateway at /prezzari)
make test      # pytest — the standard service suite
```

The whole stack builds/deploys via `docker compose build prezzari-service && up -d prezzari-service`
(UI baked into the image; no dev bind-mount).
