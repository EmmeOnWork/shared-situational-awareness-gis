# Janus stack — strangler-fig workspace

> **Public copy of my M.Sc. thesis workspace.** The Janus monolith belongs to the
> KnowMIS research lab of the University of Salerno and is not included: see
> [`monolith/README.md`](monolith/README.md). The source datasets and all local
> passwords and keys were left out as well, so the stack does not boot from this
> repository alone. The services, the edge gateway, their tests and the docs are
> all here.

This repository grows new dashboard **Widget** services *around* the Janus
monolith without ever editing the monolith's code. Each Widget strangles one
slice of the monolith's routes — and, where it ships its own UI, one slice of
the frontend too — behind a single same-origin edge gateway. The demographic
Widget was the first; [`docs/services/`](docs/services/README.md) has the
current roster.

This file is the **map**. It points into the docs that hold the depth; read the
branch you need rather than this whole tree. **All documentation lives under
[`docs/`](docs/)** — code folders hold no docs of their own, so this is the one
place to look.

## Layout

| Folder | What lives here |
| ------ | --------------- |
| [`monolith/`](monolith/) | The Janus backend + Next frontend, **untouched** (its code, not its data). The strangler fig grows around this. *Not included in this public copy — the folder holds only a note.* |
| [`services/`](services/) | The Widget deployables — code only (data + UI + tests). What each one does lives in [`docs/services/`](docs/services/README.md). |
| [`edge-gateway/`](edge-gateway/) | The single same-origin front door (Caddy) — code + Caddyfile only. How it routes lives in [`docs/edge-gateway/`](docs/edge-gateway/README.md). |
| [`docs/`](docs/) | Every doc in the workspace: architecture, the services context map, decision records, the gateway. |
| `data/` | Source CSVs and the Postgres dump used to seed the shared database locally. *Not included in this public copy.* |
| `docker-compose.yml` | Brings the whole stack up on one network with the gateway as the only published port. |

## Start here

- **Why the project is shaped this way** → [Architecture](docs/architecture/README.md),
  starting with [the strangler-fig strategy](docs/architecture/strangler-fig.md): the
  monolith stays the default for every unclaimed route, a Widget takes over a slice by
  claiming one fresh URL prefix, and strangling a route is a one-line, reversible move
  in the gateway's route table. [Full-stack Widget microservices](docs/architecture/widget-microservice-fullstack.md)
  covers the other half — how a Widget also owns and serves its own UI, the one generic
  seam the monolith needed for that (and only that, once), and the recipe every new
  Widget repeats.
- **What each Widget does, and how they relate to each other and the monolith** →
  [`docs/services/`](docs/services/README.md) — one entry per service (what it owns:
  nothing, a cache, or tables; any external dependency), plus the cross-widget
  relationships. Each service then has its own branch (e.g.
  [`docs/services/round-service/`](docs/services/round-service/README.md)) with that
  service's own decision records.
- **How a request finds its Widget (or falls through to the monolith), and how to run
  the stack** → [`docs/edge-gateway/`](docs/edge-gateway/README.md): today's routes,
  `docker compose up`, the routing-contract tests, and realtime (WebSocket/SSE).
- **Why a specific system-wide call was made** → [`docs/adr/`](docs/adr/README.md) — the
  decision records behind the gateway and the shared database.
