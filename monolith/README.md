# Monolith — not included in this public copy

This folder is intentionally empty.

In the working repository it holds the **Janus monolith** (FastAPI backend and
Next.js frontend) that the services in [`../services/`](../services/) grow
around. The monolith was developed at the KnowMIS research lab of the
University of Salerno and is not mine to publish, so its source code has been
removed from this repository and from its whole commit history.

Left out for the same reason:

- the source datasets and database dumps (`data/`);
- every local password and signing key, replaced with `CHANGE_ME` in
  `docker-compose.yml`, `.env.example` and the docs.

What this means in practice:

- `docker compose up` does not work from this copy alone: the compose file
  still builds `./monolith/backend` and `./monolith/frontend`.
- Commits that only touched the monolith are missing from the history, so a
  few commit messages mention changes you cannot see here.
- Everything else is complete: the services, the edge gateway, their tests and
  the documentation under [`../docs/`](../docs/).
