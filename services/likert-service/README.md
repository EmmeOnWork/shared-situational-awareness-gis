# likert-service — Scala Likert Widget

A read-mostly full-stack Widget (gateway prefix `/likert`, ADR-0002) that shows the
**Gradimento** — how well-received the **Active Vocazione** is on the clicked
**comune** — on a red→green gauge with a needle, emoji, star average and a one-word
label. The Gradimento is the volume-weighted average of the online star-ratings of
that Vocazione's market **Competitors** in the comune (see [CONTEXT.md](CONTEXT.md)
and [ADR-0001](docs/adr/0001-gradimento-from-cached-google-ratings-of-competitors.md)).

This is the **tracer skeleton** slice (`.scratch/likert-service/tasks/01`): the data
route returns a **hard-coded** Gradimento so the widget is demoable end-to-end. Real
comune resolution, the competitor set, the cached ratings and the refresh worker land
in later slices.

## Surface

- `GET /health` — liveness.
- `GET /likert/widget.js` — the `<likert-widget>` UI bundle. **Unguarded** (a browser
  `<script>` carries no token), served `Cache-Control: no-cache`.
- `GET /likert/gradimento?lat&lng&vocazione` — the single data route. **JWT-guarded**
  (copied monolith verify, authentication-only). Returns the Gradimento payload.

The element consumes the Active Vocazione off the generalized selection bus
(`praim:selection:vocazione`, ADR-0005) and the clicked point off the host-set
`lat`/`lng`; it needs both before it calls the route, and it ignores the Active
Workshop.

## Develop & test

```sh
make ui      # build the <likert-widget> bundle into src/static/ (served locally)
make run     # uvicorn on :28007 with reload
make test    # pytest (tier-4 suite: health/openapi/auth/catalog/bundle + the stub route)
cd ui && npm test   # node:test for scale.ts (the gauge mapping)
```

## Deploy

Baked into the image (no dev bind-mount). After a change:

```sh
docker compose build likert-service && docker compose up -d likert-service
```

Catalog self-registration is best-effort on boot; with `REGISTER_IN_CATALOG=false`
or a DB role that can't write `dashboards_config`, apply
[catalog/widget-type.sql](catalog/widget-type.sql) once instead.
