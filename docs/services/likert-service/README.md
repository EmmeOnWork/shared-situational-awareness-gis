# Scala Likert

**What it is** — `likert-service` is the Scala Likert Widget: a read-mostly gauge
widget (gateway prefix `/likert`, see [ADR-0002](../../adr/0002-edge-gateway-single-front-door.md))
that shows the **Gradimento** — how well-received the Active Vocazione is on the
clicked comune. It is the first Widget with an external-data dependency (Google
Places) and the first read-side Widget to own its own cache tables.

**When to read it** — when you're building or touching this widget.

## How it works

Despite the name, the Scala Likert is a continuous red→green rating **gauge** with
a needle, emoji and star average — not a discrete psychometric Likert scale; the
product name stuck anyway. It shows nothing until it has both of its inputs:

- the **Active Vocazione**, consumed off the generalized selection bus
  (`praim:selection:vocazione`, [ADR-0005](../../adr/0005-generalize-selection-bus.md))
  — one of the 16 Vocazioni, or none;
- the clicked **comune**, delivered as the host-set `lat`/`lng` of the click (the
  same point every Widget receives) and resolved server-side to a monolith region
  (`area_type_id = 3`) by `comune_resolver.py`.

It never consumes the Active Workshop — it isn't a sensitive widget, and it isn't
about any specific Bene.

**Gradimento** is the volume-weighted average of the 1–5 online star-ratings of
that Vocazione's **Competitor** POIs in that comune — `Σ(ratingᵢ × nᵢ) / Σ nᵢ` over
each rated competitor's stars (`ratingᵢ`) and review count (`nᵢ`), so a busier
competitor weighs more. Nobody rates a Vocazione directly; this is a
market-reception proxy read off the businesses that already perform that function
locally. It is exactly one value, or **none** ("dati insufficienti") when too few
competitors are rated, and low-confidence ("pochi dati") below a small review
floor. Civic Vocazioni (Osservatorio, Protezione Civile, Hub dei Diritti) have no
genuine market competitor, so their Gradimento is empty or unreliable by
construction. Gradimento is a different axis from **Consensus** (round-service's
internal voting agreement) and from the Active Vocazione itself (the page filter)
— same 16-Vocazione catalog, three unrelated notions.

**Competitor** resolution reuses — by copying, per the strangler pattern, not by
importing monolith code — the same `vocazione_competitors` prefix map and
comune-scoped POI join (`regions → region_areas → areas → poi_area_lookup →
pois`) that the monolith's Concorrenza map layer already paints;
`competitor_repository.py` reads that join directly off the shared DB.

**Ratings cache.** The only ratings already in the stack (the monolith's MongoDB
`POIS_F&D_reviews`) are food-and-drink only — too narrow, since competitors span
spas, offices, galleries and clinics — so ratings are sourced from **Google
Places** instead. Our POIs are foursquare-native with no shared key with Google,
so each Competitor POI is fuzzy-matched to a Google Place by name + coordinates;
the resolved `google_place_id` is stored permanently (allowed by Google's terms),
and its `rating` + `user_ratings_total` are cached with a **≤30-day TTL**. A
background worker (`refresh_worker.py`, `make refresh`) refreshes the whole
competitor universe — all comuni — every cycle, capped at a monthly call-budget,
so the data route only ever reads the cache and the widget itself never calls
Google live. See [ADR-0001](adr/0001-gradimento-from-cached-google-ratings-of-competitors.md)
for why Google Places, fuzzy matching and a background-refreshed pooled cache
were chosen over the alternatives (live-per-click, Foursquare-keyed, widening the
Mongo pipeline, Bayesian shrinkage, …).

### Routes

- `GET /health` — liveness.
- `GET /likert/widget.js` — the `<likert-widget>` UI bundle. Unguarded (a browser
  `<script>` carries no token), served `Cache-Control: no-cache`.
- `GET /likert/gradimento?lat&lng&vocazione` — the single data route. JWT-guarded
  (copied monolith verify, authentication-only). Returns the Gradimento payload.

### Owned tables

The first read-side Widget to own tables — a derived, disposable cache, fully
re-buildable from Google, not source-of-truth:

- `likert_poi_place(poi_id PK, google_place_id, match_confidence, no_match,
  matched_at)` — the permanent POI→Google identity map; `no_match=true` records an
  unmatchable POI so the refresh worker doesn't re-resolve it every cycle.
- `likert_place_rating(google_place_id PK, rating, user_ratings_total,
  fetched_at)` — the TTL'd ratings cache; `fetched_at` drives the ≤30-day TTL and
  the widget's "aggiornato il …".

`poi_id` references `public.pois(id)` by id only — no cross-domain FK into the
monolith's `pois` ([ADR-0001, shared database](../../adr/0001-shared-database.md):
every Widget re-syncs rather than joins across services).

## Running it

```sh
make ui       # build the <likert-widget> bundle into src/static/ (served locally)
make run      # uvicorn on :28007 with reload
make test     # pytest (health/openapi/auth/catalog/bundle + the gradimento route)
make refresh  # one background refresh pass: resolve new competitor identities, then
              # refresh ratings past TTL up to MONTHLY_BUDGET; schedule on cron per TTL period
make build    # docker build -t praim/likert-service .
cd ui && npm test   # node:test for scale.ts (the gauge mapping)
```

Env vars: `GOOGLE_API_KEY` (Google Places key), `TTL_DAYS` and `MONTHLY_BUDGET`
(cache TTL and the refresh worker's monthly call-budget cap), and
`REGISTER_IN_CATALOG` (set `false` to skip catalog self-registration on boot).

**Dockerfile** is a two-stage build: a `node:20-slim` stage builds the
`<likert-widget>` bundle, then a `python:3.12-slim` stage runs the FastAPI service
that serves both the API and that bundle. It copies only its own `src` and shares
no code with the monolith. Own dev port `28007` (after monolith 28000, demographic
28001, characteristic/reuse 28002, vocazione 28003, notification 28004, round
28005, geo-layers 28006).

**Deploy.** Baked into the image (no dev bind-mount). After a change:

```sh
docker compose build likert-service && docker compose up -d likert-service
```

**Catalog self-registration** is best-effort on boot: it upserts one row into the
shared `dashboards_config.widget_types`, pointing the monolith's `RemoteWidget`
seam at `/likert/widget.js` / `<likert-widget>` — no monolith code touched. With
`REGISTER_IN_CATALOG=false`, or a DB role that can't write that schema, apply
`catalog/widget-type.sql` once instead — the same upsert, kept in sync by hand.

### Database

`likert-schema.sql` is the schema-only DDL (plus DML grants) for the two owned
`likert_*` tables above. It is applied by the compose `likert-schema-init`
one-shot on every bring-up — **not** by the service at runtime — so the service
only ever issues DML, never DDL. It grants the service's DB role
`SELECT`/`INSERT`/`UPDATE` (the worker upserts, the route reads — no `DELETE`; a
stale row is overwritten in place); the role defaults to the local `janus`, and
the compose one-shot passes the real one via `-v service_role=...`. Idempotent:
re-running it on an existing database is a no-op (`CREATE TABLE IF NOT EXISTS`;
grants are re-asserted; loads no data).

## Links out

- [Decision records](adr/)
- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
