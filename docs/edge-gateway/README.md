# Edge gateway

**What it is** — the single same-origin front door for the Janus stack: a dumb
Caddy reverse proxy, deployed as its own component outside both monolith
repos. The browser only ever talks to this origin. See
[ADR-0002](../adr/0002-edge-gateway-single-front-door.md).

**When to read it** — before adding a widget's route, running the stack
locally, or touching realtime (WebSocket/SSE) auth.

## Routing

The routing map lives in exactly one file,
[`Caddyfile`](../../edge-gateway/Caddyfile): explicit prefixes route to widget
services, the monolith's enumerated prefixes come next, and the Next frontend
is the catch-all default. The site address and every upstream are injected per
environment (`{$VAR}`), so the same file runs unchanged locally, in staging,
and in prod.

Routes today: `/demographics`, `/characteristic`, `/reuse`, `/vocazione`,
`/notifications`, `/rounds`, `/likert`, `/prezzari`, `/geo-layers` each go to
their own service; everything else falls through to the monolith, except the
frontend's own paths (served by Next). Adding a widget is a one-line Caddyfile
addition — see [Full-stack Widget microservices](../architecture/widget-microservice-fullstack.md).

## Per-environment config: base URL & TLS

Promoting local → staging → prod is a configuration change, not a code change.

- **Frontend base URL → the gateway.** `NEXT_PUBLIC_BACKEND_URL` points at the
  gateway, never at the monolith backend directly, so both framework calls
  (`/dashboards`, `/auth`) and Widget calls (`/demographics`) leave the browser
  as relative paths against one origin. Compose defaults to the local gateway
  (`http://localhost:8080`); staging/prod inject their own.
- **Relative paths only — enforced.** `resolveUrl` passes any `http(s)://` URL
  through untouched ([`fetch-wrapper.ts`](../../monolith/frontend/src/lib/fetch-wrapper.ts)),
  so an absolute URL in a dashboard config would silently bypass the gateway
  (second origin, no TLS, CORS back).
- **TLS is the injected site address** — `GATEWAY_SITE_ADDRESS` is the toggle:

  | Environment | `GATEWAY_SITE_ADDRESS` | Result |
  | --- | --- | --- |
  | local / tests | `:8080` (port-only) | plain HTTP, no cert friction |
  | staging / prod | a hostname | Caddy's automatic HTTPS; realtime is WSS for free |

## Running the full stack (compose)

The top-level [`docker-compose.yml`](../../docker-compose.yml) wires the
gateway, every widget service, the monolith backend, and the Next frontend on
one network. **The gateway is the only published port**
(`http://localhost:8080`); everything else is reachable only server-to-server.

```bash
docker compose up --build
```

The compose contract (single published port, upstreams = service names,
Caddyfile reused unchanged) is guarded by
[`tests/test_compose_stack.py`](../../edge-gateway/tests/test_compose_stack.py),
which reads the compose file directly — no Docker daemon needed.

## Routing-contract tests

A pytest harness launches the real Caddy binary in front of tiny echo
upstreams and asserts *which upstream answered* — the route table can be
rewritten, or the proxy swapped, without touching the tests.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Needs the **Caddy binary**: located via the `CADDY_BIN` env var, falling back
to `caddy` on `PATH`. If neither resolves, the live-gateway tests skip with a
clear message. To pin a local path, copy `.env.example` to `.env` and set
`CADDY_BIN` (git-ignored; the harness loads it automatically).

## Realtime (WebSocket/SSE)

Caddy's `reverse_proxy` carries WebSocket/SSE upgrades natively on every
route — no gateway config beyond the proxy directive it already has.

### Realtime auth convention

Realtime connections authenticate with the monolith JWT,
verified by the **owning Widget service**, exactly like HTTP — never via
Supabase Row-Level Security. The browser `WebSocket` API can't set an
`Authorization` header, so the JWT travels instead as a **query parameter**
(`?access_token=<jwt>`) or a **WebSocket subprotocol**; either way the owning
service reads and verifies it on connect.

## Links out

- [ADR-0002 — Edge gateway, single front door](../adr/0002-edge-gateway-single-front-door.md)
- [The strangler-fig strategy](../architecture/strangler-fig.md)
- Back to [Architecture](../architecture/README.md)
