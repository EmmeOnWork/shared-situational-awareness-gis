# Janus stack — strangler-fig workspace

This repository grows new dashboard **Widget** services *around* the Janus
monolith without ever editing the monolith's code. New services strangle the
monolith one route at a time, behind a single same-origin edge gateway. The
demographic Widget is the first such service.

This file is the **map**. It points into the docs that hold the depth; read the
branch you need rather than this whole tree.

## Layout

| Folder | What lives here |
| ------ | --------------- |
| [`monolith/`](monolith/) | The Janus backend + Next frontend, **untouched** (its code, not its data). The strangler fig grows around this. |
| [`services/`](services/) | The new Widget deployables. Today: [`demographic-service/`](services/demographic-service/README.md). |
| [`edge-gateway/`](edge-gateway/README.md) | The single same-origin front door (Caddy). The seam that routes each request to the monolith or a Widget. |
| [`docs/`](docs/architecture/README.md) | Architecture decisions, the strangler-fig strategy, and the review that started it. |
| [`data/`](data/) | Source CSVs and the Postgres dump used to seed the shared database locally. |
| `docker-compose.yml` | Brings the whole stack up on one network with the gateway as the only published port. |

## Start here

- **Why the project is shaped this way** → [Architecture](docs/architecture/README.md),
  starting with [the strangler-fig strategy](docs/architecture/strangler-fig.md).
- **The shared vocabulary** (Territory, Widget, DataResponse, …) → [`CONTEXT.md`](CONTEXT.md).
- **Run the stack** → [`edge-gateway/README.md`](edge-gateway/README.md) (compose, reachability smoke).
