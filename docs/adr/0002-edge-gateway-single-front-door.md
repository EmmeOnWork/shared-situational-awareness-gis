# An edge gateway is the single front door for the frontend, monolith, and widget services

Status: accepted

To let new widget services strangle the monolith without anyone editing it, we
introduce an **edge gateway**: a dumb reverse proxy (Caddy) deployed as its own
top-level component, **outside** `monastero-janus-backend` and
`monastero-janus-frontend`. It is the single origin the browser ever talks to.
It serves the Next frontend at `/`, routes a small set of explicit path
prefixes to widget services (`/demographics` → demographic-service, future
`/rounds`, `/notifications`, `/geo-layers`, …), and sends **everything else to
the monolith backend** as a catch-all. The same artifact runs in local, staging,
and production — only configuration (hostname, upstream addresses, TLS) differs.

This builds on ADR-0001: the monolith stays untouched (its **code**, not its
data), and every service keeps verifying monolith-issued JWTs. The only change
on the monolith side is the deployment value `NEXT_PUBLIC_BACKEND_URL`, which
now points at the gateway instead of the backend directly — a build-time config
value, not a code change.

## Considered options

- **No seam — wire widgets with absolute URLs in dashboard config (status quo
  mechanism).** Rejected: `resolveUrl` passes `http(s)://` URLs through
  untouched, so each widget's host leaks into the monolith's Mongo-stored
  dashboard documents. Routing ends up scattered with no module that owns it,
  and the frontend gains a second origin per service.
- **A Backend-for-Frontend (BFF).** Rejected: the widget services already speak
  the canonical `DataResponse` contract, so there is no aggregation or response
  reshaping for a BFF to do. Its extra power would sit unused while becoming a
  tempting place for widget logic to pool — a second monolith in waiting. The
  gateway is deliberately kept incapable of holding logic.
- **Gateway fronts only the new services; monolith stays directly addressed.**
  Rejected: the browser picks one base URL, so this leaves the frontend with two
  origins and still bakes a host into config. It throws away the single-origin
  win.
- **Two-origins / per-environment CORS (frontend a separate deployable).**
  Rejected: with three environments, a per-env CORS allowlist is three places to
  keep correct and prone to drift. Uniform same-origin makes CORS structurally
  impossible instead.
- **Realtime via Supabase Realtime direct from the browser.** Rejected: it forks
  authorization to the Supabase token + Row-Level Security, away from the
  monolith-JWT + `scopes` model the whole design rests on, and adds a second
  origin for realtime. Realtime instead rides through the gateway to the owning
  widget service, which verifies the monolith JWT like every other service.
- **Edge gateway as a dumb same-origin front door (chosen).** One origin, one
  routing map, no CORS anywhere, TLS terminated in one place, monolith and its
  JWT contract untouched.

## Consequences

- **The routing map lives in exactly one file** (the `Caddyfile`). Adding a
  widget service is one line: register a fresh top-level prefix. A new service
  may **not** reuse a monolith prefix (e.g. `/layers` belongs to the monolith;
  a new layers service must claim something like `/geo-layers`).
- **The monolith stays the default.** Unknown prefixes fall through to the
  monolith backend, so the monolith can add routes with **zero** gateway
  changes — the gateway respects the same "don't touch me as I evolve" contract
  the monolith does.
- **Dashboard configs must use relative paths only.** The `http(s)://`
  passthrough branch in `resolveUrl` becomes a footgun: any absolute URL in a
  config silently bypasses the gateway. "No absolute URLs in dashboard config"
  is now an enforced convention.
- **Widget services become non-browser-facing and carry no CORS.** The browser
  only ever calls the gateway (same origin), so server-to-server calls from the
  gateway to a service are not subject to browser CORS. This removes the
  demographic service's wide-open CORS by construction, rather than tightening a
  regex.
- **The gateway is the TLS-termination point** in staging/production; services
  stay plain HTTP behind it, and realtime is WSS for free.
- **The gateway must support WebSocket/SSE upgrade** (Caddy does), because
  realtime notifications and decisional rounds flow through it. Browser
  WebSocket cannot set an `Authorization` header, so realtime auth passes the
  monolith JWT another way (query param / subprotocol), verified by the owning
  service.
- **The gateway is a new single point of failure** on the critical path of all
  traffic, including the previously-stable monolith. This is the normal,
  understood cost of a reverse proxy; it is mitigated by choosing a
  battle-tested one and treating it as *replacing* the existing prod ingress,
  not stacking a new tier on top.
- **`NEXT_PUBLIC_BACKEND_URL` is inlined at build time**, so each environment
  needs its own build-time value (or a runtime-injected config), not one image
  reused across all three.
