# Realtime Notifier

**What it is** — `notification-service` (URL prefix `/notifications`) is a
standalone, stateless / ephemeral realtime Widget: it holds an authenticated
WebSocket connection and renders self-describing Notifications — a top-right
toast plus an audio alert — pushed from the server. It owns no tables.

**When to read it** — when you're building or touching this widget, or
producing Notifications into it from another service (e.g. `round-service`).

## How it works

A **Notification** is a single transient, fire-and-forget alert: never
stored, never replayed on reconnect. It is self-describing — the Notifier
understands only a **Severity** (`info | warning | success`, mapping to a
sound + colour) plus `title`/`body` text, and optionally a **Scope**; it
never sees a domain event type (it never sees e.g. `round_closed`), because
the producer — the future Round Manager
([round-service](../round-service/README.md)) — classifies its own domain
event into a Severity before it ever reaches here.

**Scope** is an optional addressing hint expressed against a selection-bus
axis, e.g. `{ axis: "workshop", value: <beneId> }` (both fields required — a
half-specified scope is rejected rather than silently treated as global). The
server always broadcasts to every connected client — there are **no
server-side rooms**. Instead each client filters client-side: an unscoped
Notification always renders; a scoped one renders only if the receiver's
current selection on that axis — the **Active Workshop**, published by the
Workshop Selector in [reuse-service](../reuse-service/README.md) — matches
`scope.value`; a scoped Notification is suppressed when there is no current
selection on that axis.

Unlike every other Widget, this one is not a grid card: it mounts as a
**chromeless, page-global overlay** via the dashboard's second generic seam,
`<RemoteOverlay>` ([ADR-0006](../../adr/0006-page-global-overlay-seam.md)). A
catalog row flagged `placement: "overlay"` inside `default_props` (instead of
a grid card) tells the monolith to mount the bundle page-global and invisible
until a toast arrives, carrying the same `token`/`base` contract the grid
seam already feeds card Widgets.

Two realtime surfaces sit under `/notifications`, both thin glue over a
single in-memory `ConnectionHub` fan-out:
- `/notifications/ws` — the WebSocket endpoint clients subscribe to. The
  handshake must carry a valid monolith-issued JWT
  ([ADR-0002](../../adr/0002-edge-gateway-single-front-door.md)), as either
  the `?access_token=` query param or an `access_token` subprotocol pair; a
  missing/invalid token is refused (WS close code 1008) before the
  connection is ever registered with the hub.
- `POST /notifications/publish` — the **publish ingress**: validates a
  Notification body (`severity`, `title`, `body`, optional `scope`; FastAPI
  422s a malformed one) and fans it out to every connected client, returning
  `{"delivered": <count>}`. The expected caller is an automated server-side
  producer, never an end user; authorization on who may call it is a
  separate, deferred decision.

## Running it

Full-stack Widget: a Node stage builds the `<notification-overlay>` custom
element bundle; a Python/FastAPI stage serves it plus `/health` and the
realtime routes above.

- **Backend** — Python 3.12, FastAPI, plus `pyjwt`/`cryptography` for JWT
  verification (on top of the shared `fastapi[standard]` /
  `uvicorn[standard]` / `pydantic` / `pydantic-settings` / `sqlalchemy` /
  `psycopg[binary]` stack). Install with `pip install -r requirements.txt`
  (`requirements-dev.txt` adds `pytest`/`httpx`). Run with `uvicorn
  src.app:app --host 0.0.0.0 --port 28004 --reload` (or `make run`); test
  with `python -m pytest` (or `make test` — `pytest.ini` sets `testpaths =
  tests`). Tests are hermetic: `conftest.py` mints an in-memory RSA keypair
  and sets `JWT_ALGORITHM`/`JWT_VERIFICATION_KEY` before the app is imported,
  and the catalog-registration lifespan hook never fires under a plain
  `TestClient`, so no test touches a database or a real key.
- **UI** — Node 20, plain esbuild, no framework. From `ui/`: `npm install`,
  `npm run build` (bundles `src/notification-overlay.ts` →
  `dist/notification-overlay.js`), `npm run typecheck`, `npm test` (`node
  --test "src/**/*.test.ts"`). `make ui` builds it and copies the output to
  `src/static/` so FastAPI can serve `/notifications/widget.js` locally.
- **Docker** — `make build` (or `docker build -t praim/notification-service
  .`) runs both stages into one image; default port **28004** (monolith
  28000, demographic 28001, characteristic/reuse 28002, vocazione 28003).
- **Env vars** — `JWT_ALGORITHM` (default `RS256`) and
  `JWT_VERIFICATION_KEY` (the shared verification-only public key, mirroring
  the monolith's env-var names — this service only verifies, it never signs
  a token); `DATABASE_URL` (the shared Supabase, used solely by the
  best-effort catalog self-registration upsert into
  `dashboards_config.widget_types`); `REGISTER_IN_CATALOG` (bool, default
  `true` — set `false` to skip it and apply `catalog/widget-type.sql`
  manually instead).

## Links out
- [ADR-0006 — Page-global overlay seam](../../adr/0006-page-global-overlay-seam.md)
- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
