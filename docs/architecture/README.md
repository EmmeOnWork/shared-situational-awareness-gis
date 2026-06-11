# Architecture

How the Janus stack is shaped, and why. Read this branch when you need the
*reasoning* behind the structure — not how to operate a component (that lives in
each component's own README).

## The strategy

- [Strangler fig](strangler-fig.md) — the overarching pattern: grow new Widget
  services around the monolith, strangling it one route at a time, without ever
  editing its code. **Start here** to understand why the gateway, the shared
  database, and the per-service deployables exist as a single coherent move.
- [Full-stack Widget microservices](widget-microservice-fullstack.md) — how a
  Widget owns its **UI** as well as its data (a self-contained custom element the
  service serves), via one generic `remote` seam added to the monolith once. Read
  this to build a Widget that renders without the monolith.

## Decisions of record (ADRs)

The strategy above is realised by two accepted decisions. Each ADR is the
narrow, durable record of one choice and the options rejected:

- [ADR-0001 — Shared database](../adr/0001-shared-database.md): Widget services
  read/write the monolith's Supabase Postgres rather than owning their own
  datastore.
- [ADR-0002 — Edge gateway, single front door](../adr/0002-edge-gateway-single-front-door.md):
  one dumb reverse proxy is the only origin the browser talks to; it routes to
  the monolith (default) or a Widget (explicit prefix).

## Background

- [Architecture review (strangler fig)](../architecture-review-strangler-fig-20260601.html) —
  the review that surfaced blockers **G1** (no runtime config wiring), **G2**
  (the demographic service unreachable from the UI), and warning **G3**
  (wide-open CORS). ADR-0002 and the gateway resolve them.
