# round-service — Round Manager Widget

The first **stateful, multi-user, realtime-shared** Widget in the stack: it runs an
iterative group **consensus process** over the current **Bene** (the Active Workshop).
Behind the edge gateway under the reserved `/rounds` prefix (system ADR-0002).

See [CONTEXT.md](CONTEXT.md) for the domain language and
[docs/adr/](docs/adr/) for the service decisions
(own per-Bene WebSocket rooms, nominal-entropy consensus, internal-only result).

## This slice (task 01 — walking skeleton)

A deployable full-stack Widget with an empty state, routed by the gateway:

- `GET /health` — liveness probe.
- `GET /rounds/widget.js` — the UI bundle. **Unguarded** (a browser `<script>` load
  carries no token) and served `Cache-Control: no-cache` so a redeploy is never
  served stale.
- `GET /rounds/ping` — a JWT-**guarded** reachability probe. v1 is
  authentication-only (a valid monolith JWT, no scope — a `rounds:*` scope is out of
  scope for this PRD). The lobby/roster/vote/recap/WS routes land in later slices,
  each added behind the same guard.
- `<round-widget>` custom element: **consumes** the Active Workshop bus (never
  publishes). No Bene ⇒ empty state ("seleziona un Bene"); selecting a Bene swaps to
  that Bene's lobby placeholder. Registered in the dashboard "Add widget" catalog and
  baked into the image.

JWT verify is **copied, not imported** from the established widget pattern
(claims `sub`, `email`, `role`, `scope`).

## Develop

```sh
make ui      # build the <round-widget> bundle into src/static/ (serves /rounds/widget.js)
make run     # uvicorn on :28005 with --reload
make test    # pytest (backend)
cd ui && npm test   # node --test (UI contract)
```

## Deploy

Follows the established widget pattern: UI baked into the image, `docker compose build
round-service && docker compose up -d round-service` to deploy a change.
