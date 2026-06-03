# Edge Gateway

The single same-origin front door for the Janus stack (see
[ADR-0002](../docs/adr/0002-edge-gateway-single-front-door.md)). A dumb Caddy
reverse proxy deployed as its own top-level component, **outside** both monolith
repos. The browser only ever talks to this origin; the gateway routes explicit
path prefixes to widget services and (in later slices) sends everything else to
the monolith backend. It holds **no business logic**.

The routing map lives in exactly one file: the [`Caddyfile`](Caddyfile). The site
address (which doubles as the TLS toggle, below) and the upstream addresses are
injected per environment via Caddy env substitution (`{$VAR}`), so the same file
runs unchanged across local, staging, and prod — only configuration differs.

This is the tracer slice (task 01): a single route, `/demographics` →
demographic-service, plus the routing-contract test harness every later slice
reuses.

## Per-environment config: base URL & TLS

Promoting local → staging → prod is a **configuration change, not a code change**.
The same `Caddyfile` and the same frontend image-shape run everywhere; only injected
values differ (public hostname, upstream addresses, TLS).

**Frontend base URL → the gateway.** The browser's single origin is the gateway, so
the Next frontend's `NEXT_PUBLIC_BACKEND_URL` points at the gateway — never at the
monolith backend directly. Both framework calls (`/dashboards`, `/auth`) and Widget
calls (`/demographics`) then leave the browser as relative paths resolved against
that one origin. `NEXT_PUBLIC_*` is inlined at build, so this is a **per-environment
build-time (or runtime-injected) value** — each environment supplies its own gateway
origin, not one image reused across all three. Compose defaults it to the local
gateway (`http://localhost:8080`); staging/prod inject their own gateway URL. **No
frontend code changes** for any of this.

> **Relative paths only — enforced.** `resolveUrl` passes any `http(s)://` URL
> through untouched ([`fetch-wrapper.ts`](../monastero-janus-frontend/src/lib/fetch-wrapper.ts)),
> so an **absolute** URL in a dashboard config silently bypasses the gateway (a second
> origin, no TLS termination, CORS back). "No absolute URLs in dashboard config" is a
> load-bearing convention, not cosmetic — dashboard configs must use relative paths so
> every request resolves against `NEXT_PUBLIC_BACKEND_URL` (the gateway).

**TLS is the injected site address.** `GATEWAY_SITE_ADDRESS` *is* the per-environment
TLS toggle:

| Environment    | `GATEWAY_SITE_ADDRESS` | Result                                   |
| -------------- | ---------------------- | ---------------------------------------- |
| local / tests  | `:8080` (port-only)    | plain HTTP — no certificate friction     |
| staging / prod | `gateway.example.edu` (a hostname) | Caddy's **automatic HTTPS**, so realtime is **WSS** for free |

A port-only (or `http://…`) address serves plain HTTP; a hostname makes Caddy
provision and serve HTTPS automatically. Same routing logic, same file — flipping TLS
is just which site address gets injected. (The routing-contract harness injects the
local HTTP form, `GATEWAY_SITE_ADDRESS=:<port>`, so the suite also proves the same
file serves over plain HTTP locally.)

## Routing-contract tests

The tests treat the gateway as a **black box**: a pytest harness launches the
real Caddy binary in front of tiny echo upstreams (each answers with its own
identity), sends real HTTP to the gateway, and asserts *which upstream answered*
— never Caddy internals. So the route table can be rewritten, or the proxy
swapped, without touching the tests. The echo stubs also report the headers they
received, so a test can assert *what survived the hop* — e.g. that an
`Authorization: Bearer` token reaches the upstream byte-for-byte unchanged and
the gateway verifies nothing itself (auth is pass-through; see ADR-0002).

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The harness needs the **Caddy binary**. It is located via the `CADDY_BIN`
environment variable, falling back to `caddy` on `PATH`. If neither resolves, the
live-gateway tests **skip** with a clear message (the harness self-test still
runs). Install Caddy (e.g. `winget install CaddyServer.Caddy`) and either put it
on `PATH`, or — when it isn't — record its path once in a local `.env`:

```bash
cp .env.example .env        # then set CADDY_BIN to your binary's absolute path
python -m pytest            # the harness loads .env automatically
```

`.env` is git-ignored (paths are machine-specific); commit changes to
`.env.example` instead. Values already in the environment win, so an explicit
export or a CI value overrides the file:

```bash
# PowerShell — one-off override without touching .env
$env:CADDY_BIN = "C:\path\to\caddy.exe"; python -m pytest
```

## Running the full stack (compose)

The top-level [`docker-compose.yml`](../docker-compose.yml) (repo root) wires the
four real components — this gateway, the demographic-service, the monolith
backend, and the Next frontend — onto one shared network. **The gateway is the
only published port** (`http://localhost:8080`); every other service is reachable
only server-to-server on the internal network. The gateway reuses *this same*
`Caddyfile`, mounted read-only, with the upstreams injected as compose service
names — no second copy of the routing logic.

```bash
docker compose up --build        # one command brings up the whole stack
```

The compose contract (single published port, upstreams = service names, Caddyfile
reused unchanged) is guarded by [`tests/test_compose_stack.py`](tests/test_compose_stack.py),
which reads the compose file directly and needs **no Docker daemon**.

### Reachability smoke (demographic-service through the gateway → 200)

A liveness check that the demographic Widget is reachable through the single
origin — no real demographic data required. The demographic endpoints sit behind
the `demographics:read` scope, so mint a dev token (the compose sets a local-only
HS256 verification key, `JWT_VERIFICATION_KEY`, the service verifies against) and
call `/demographics/ping` through the gateway:

```bash
# bash — mint a dev token (PyJWT) and hit the gateway's single origin
TOKEN=$(python -c "import jwt,time; print(jwt.encode({'sub':'1','email':'dev@example.com','role':'admin','scope':'demographics:read','token_type':'access','exp':int(time.time())+3600},'CHANGE_ME',algorithm='HS256'))")
curl -i -H "Authorization: Bearer $TOKEN" http://localhost:8080/demographics/ping
# -> HTTP/1.1 200 OK   {"status":"ok"}
```

```powershell
# PowerShell equivalent
$TOKEN = python -c "import jwt,time; print(jwt.encode({'sub':'1','email':'dev@example.com','role':'admin','scope':'demographics:read','token_type':'access','exp':int(time.time())+3600},'CHANGE_ME',algorithm='HS256'))"
curl.exe -i -H "Authorization: Bearer $TOKEN" http://localhost:8080/demographics/ping
```

A `200` proves the path end-to-end: the single origin routed `/demographics` to
the demographic-service (via the injected compose service name), the gateway
passed the Bearer token through untouched, and the service verified it and
answered — all without the `public.demographic` table being seeded. If
`JWT_VERIFICATION_KEY` is overridden in the environment, sign the token with that
value instead of the dev default.

## Realtime (WebSocket/SSE)

Caddy's `reverse_proxy` carries WebSocket and SSE **upgrades natively on every
proxied route** — the gateway needs *no* configuration or logic beyond the proxy
directive it already has. So the future realtime Widgets (notifications,
decisional rounds) ride the same single origin for free: each registers its own
fresh prefix (the usual one-line change) and holds its own WS/SSE connection
behind the gateway. The gateway gains nothing for realtime beyond what routing
HTTP already gave it. The routing-contract suite proves the upgrade passes
through end-to-end (`test_websocket_upgrade_passes_through_gateway`) so this can
never silently regress before the first realtime Widget exists.

### Realtime auth convention

Realtime connections authenticate with the **monolith JWT**, verified by the
**owning Widget service** — exactly like HTTP requests, and *not* via Supabase
Row-Level Security (see [ADR-0002](../docs/adr/0002-edge-gateway-single-front-door.md)
and [ADR-0001](../docs/adr/0001-shared-database.md)). The gateway verifies
nothing; it only carries the upgrade.

The wrinkle: the browser `WebSocket` API **cannot set an `Authorization`
header**, so the Bearer pass-through that HTTP relies on is unavailable for the
handshake. The JWT is therefore passed another way the browser *can* control:

- as a **query parameter** on the connect URL
  (e.g. `…/notifications?access_token=<jwt>`), or
- as a **WebSocket subprotocol** (`Sec-WebSocket-Protocol`).

Either way the **owning Widget service** reads and verifies the token on connect.
This is a convention for the realtime Widget services to follow; it requires no
gateway capability beyond the WebSocket upgrade itself.
