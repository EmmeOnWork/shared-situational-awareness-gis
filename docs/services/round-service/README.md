# Round Manager

**What it is** — `round-service` is the first **stateful, multi-user, realtime-shared**
Widget in the Janus strangler-fig stack, behind the edge gateway under the reserved
`/rounds` prefix (system [ADR-0002](../../adr/0002-edge-gateway-single-front-door.md)).
It runs an iterative group **consensus process** over the current **Bene**: it owns
its own tables and runs its own authenticated per-Bene WebSocket room, rather than
reusing the page-global selection bus or the Realtime Notifier's broadcast transport.

**When to read it** — when you're building or touching this widget (`services/round-service/`).

## How it works

The service exposes:

- `GET /health` — liveness probe.
- `GET /rounds/widget.js` — the `<round-widget>` UI bundle. Deliberately **unguarded**
  (a browser `<script>` load carries no bearer token) and served with
  `Cache-Control: no-cache` so a redeploy is never served stale.
- `GET /rounds/ping` — a JWT-guarded reachability probe, authentication-only (see
  Auth below).
- `GET /rounds/ws/{poi_id}` — the per-Bene WebSocket carrying the whole live lobby →
  voting → recap → consensus lifecycle plus the anonymous Chat (self-guarded — see
  Per-Bene WebSocket room below).

`<round-widget>` is a standard custom element, available through the DB-driven
widget catalog (there is no in-app "Add widget" menu) and baked into the image; it
renders whichever phase its Bene's room is currently in.

### Domain language

- **Bene** — the confiscated/public building (a special POI) a Round is about,
  owned by the Building Characteristic context. The current Bene is the **Active
  Workshop**.
- **Participant** — a user taking part in a Bene's consensus process. The roster is
  self-forming: there is no per-Bene access list (access is scope-granular —
  `reuse:read` exposes *every* Bene), so a user becomes a Participant by **joining**
  this Bene's round. Identified by the JWT `sub` (user_id); the Round Manager owns
  this membership since no existing table models it.
- **Role** (stakeholder Role) — the participatory-workshop category a Participant
  holds: `tecnico`, `istituzionale`, `economico` — a closed catalog of three. It is
  the recap radar's branches and the grouping for intra-Role Consensus. Distinct
  from the JWT auth `role`: it's chosen once at registration in the monolith,
  persisted on `public.users`, carried on the JWT as the **`stakeholder_role`**
  claim, and read off the verified handshake at `join` — there is no in-lobby Role
  declaration (a legacy token minted before the claim existed is rejected at join;
  the user re-logs in to refresh it).
- **Round** — one decisional voting cycle over the current Bene: every Participant
  casts one **Vote**, the Round closes once all have voted, a **Consensus** value
  is computed, and — unless it's already 100% — a new Round begins after
  deliberation. Round state and history are per-Bene and persistent. The roster
  ("N") is **frozen for the Round's duration** and can change only *between*
  Rounds; a user who joins mid-Round enters the *next* Round, never the current
  one. Round 1 opens through a lobby (join, ready, start); every later Round opens
  through the same ready-gate. Rounds repeat with no upper bound until Consensus =
  100%. There is deliberately **no escape hatch yet**: no timeout, facilitator
  force-close, or below-100% quorum — a single Participant who never votes blocks
  that Bene's process indefinitely. Accepted for now (reversible/additive, so not
  its own ADR).
- **Vote** — a Participant's chosen Vocazione for the current Round, picked from
  the same 16-archetype catalog the Vocazione Selector owns — a private ballot,
  never published on the selection bus and never the Active Vocazione (same
  options, different axis: the Active Vocazione is a page-global filter lens, a
  Vote is a secret per-Round choice). **Final on confirmation** (the confirm modal
  is the point of no return) — it cannot change within the Round; changing one's
  mind happens in the *next* Round, after deliberating in the Chat.
- **Consensus** — a nominal, exact-match measure of agreement among Participants'
  Votes: two Participants agree only if they chose the *same* Vocazione (the 16
  archetypes are a nominal catalog with no defined distance, which rules out
  ordinal measures). See Consensus computation below and this service's
  [ADR-0002](adr/0002-nominal-entropy-consensus.md) for the formula and why.
- **Winning category** — the single Vocazione everyone converged on when Consensus
  reaches 100%. See Consensus result stays internal below and this service's
  [ADR-0003](adr/0003-consensus-result-stays-internal.md).
- **Chat** — a per-Bene, continuous anonymous message stream spanning *all* of the
  Bene's Rounds (the deliberation log that lets Participants change their mind
  between Rounds). Write access unlocks only after the Participant has cast their
  Vote in the current Round (preserves Vote independence — you can't read others'
  arguments before voting); stays read-only in the recap. Anonymity is total: no
  author is ever shown; the server retains the author's user_id internally for
  abuse control only and never exposes it.

### Round lifecycle (engine)

Implemented as a small pure state machine (`src/engine/round_engine.py`) over four
phases: `lobby` (round_number 0, no Round open) → `voting` (Round open, roster
frozen) → `recap` (Round closed, Consensus < 100%; doubles as the next Round's
lobby) → `consensus` (terminal, Consensus = 100%). Events: `Join` (adds a
Participant with the Role taken from the verified JWT), `Ready`, `OpenRound`
(needs ≥2 ready Participants — a solo Round has nothing to reach consensus about —
freezes the roster and opens the next Round), `CastVote` (a roster member's final
ballot; the last (N/N) Vote closes the Round: unanimous ballots emit
`ConsensusReached` with the `winner` and how many `rounds` it took, otherwise
`RoundClosed` and every Participant's ready flag resets for the next ready-gate).

### Consensus computation

Computed once a Round closes (`src/consensus/consensus.py`,
`src/engine/recap.py`) as **one minus normalized Shannon entropy** of the vote
distribution:

`C = 1 − H / ln(min(n, k))`, `H = −Σ pᵢ ln pᵢ`

— `n` = voters at that level, `k` = 16 (the Vocazione catalog size). Normalizing
by the *realizable* maximum `ln(min(n,k))`, not a fixed `ln k`, keeps `C = 0`
reachable at maximal dispersion and `C = 1` iff unanimity at any group size (a
single-person Role reads as `C = 1`). Computed at two levels per Round: **per
Role** (the recap radar's branch intensities — intra-role cohesion) and **pooled
over all Participants** ("consenso totale" — the measure on the pooled votes, not
an average of the per-Role values). See this service's
[ADR-0002](adr/0002-nominal-entropy-consensus.md) for why nominal exact-match +
entropy was chosen over an ordinal measure like Tastle–Wierman.

Every closed Round persists its raw outcome to `public.round_outcomes`
(`db/round-schema.sql`): `poi_id`, `round_number`, `n`, `votes_by_role` (jsonb,
raw per-Role×Vocazione counts), `per_role_consensus` (jsonb), `overall_consensus`,
`duration_seconds`, `recorded_at`; primary key `(poi_id, round_number)`, written as
an idempotent upsert so a replayed close never duplicates a row. This makes the
whole instrument re-derivable offline — an alternative measure can be recomputed
from the stored distributions. The *live* Round (roster, in-progress votes, chat)
lives only in the per-Bene room's memory: only a **closed** Round's outcome
reaches the database.

### Per-Bene WebSocket room

`GET /rounds/ws/{poi_id}` carries the whole live lobby → voting → recap →
consensus lifecycle, one room per Bene, owned in-memory by a single
process-wide `RoomManager` (`src/rooms/room_manager.py`). A browser can't set an
`Authorization` header on a WS handshake, so unlike the HTTP routes this one is
mounted unguarded and **self-guards**: the JWT rides `?access_token=` or an
`access_token` subprotocol sentinel, verified with the same key before the
connection joins any room; the identity (`user_id`, stakeholder Role) comes only
from that verified handshake, never from message bodies.

Client → server messages: `{"type": "join"}`, `{"type": "ready"}`,
`{"type": "start"}`, `{"type": "vote", "vocazione": "<id>"}`,
`{"type": "chat", "body": "<text>"}`. Server → client, on every change, a
**per-recipient** projected view (never one shared broadcast): `phase`,
`round_number`, `ready_count`, `n`, `voted_count`, `remaining_count`,
`voted_user_ids`, `participants` (`user_id`/`role`/`ready`), `recap`
(`{radar: [{role, consensus, count}], overall, n}`, present once a Round has
closed), `consensus` (`{winner, rounds}`, present only in the terminal phase),
and `chat` (the anonymised stream — empty for anyone who hasn't voted yet this
Round). A rejected action gets `{"type": "error", "detail": "..."}` back, alone.
This is how Vote independence is enforced at the wire, not just in the UI: nobody
sees Vote *content* before the recap (only counts + who's voted), and nobody reads
Chat before casting their own Vote.

See this service's [ADR-0001](adr/0001-own-websocket-per-bene-rooms.md) for why
the Round Manager runs its own transport — deliberately breaking the Realtime
Notifier's no-server-side-rooms rule — instead of polling or reusing the
Notifier's socket.

### Active Workshop (consumed, never published)

`<round-widget>` is a **sensitive widget**: it consumes the page-global Active
Workshop (system [ADR-0003](../../adr/0003-active-workshop-selection-bus.md),
generalized by [ADR-0005](../../adr/0005-generalize-selection-bus.md)) and never
publishes it. No Bene selected ⇒ empty state ("seleziona un Bene") — no Bene, no
room, no Round. Selecting one opens that Bene's room and renders whichever phase
it's in; switching Bene re-subscribes the widget to the new room (a Vote already
cast on the previous Bene stays valid — Votes are per-Bene).

### Notifications produced

The backend is the server-side **producer**: it POSTs to the Realtime Notifier's
publish ingress (`http://notification-service:28004/notifications/publish`,
server-to-server — not through the gateway) for the shared lifecycle moments
only, each carrying the Bene's Scope `{"axis": "workshop", "value": "<poi_id>"}`
so only Participants whose Active Workshop is that Bene see the toast / hear the
sound:

| Engine effect | severity | title | body |
|---|---|---|---|
| `RoundOpened` | `info` | Nuovo round | È iniziato un nuovo round di votazione. |
| `RoundClosed` | `info` | Round chiuso | Tutti hanno votato: il round è chiuso. |
| `ConsensusReached` | `success` | Consenso raggiunto | Il gruppo ha raggiunto il consenso totale. |

A **Vote carries no Notification** — a non-closing Vote emits no engine effect at
all, so confirming one is purely local widget feedback (the modal → "HAI VOTATO"
transition): the Notifier broadcasts globally and can't target a single voter, and
a per-Vote sound would be noise. Both this POST and the `round_outcomes` write are
best-effort: a Notifier or DB hiccup is logged and never breaks a live Round.

### Consensus result stays internal

At 100% Consensus the winning Vocazione is persisted in this service's own
history (derivable from the unanimous `round_outcomes` row) and shown in the
recap — but **no cross-context Bene → Vocazione link** is written for Building
Characteristic, the Vocazione Selector, or a future map layer to consume. The
deferred map-layer link stays deferred until a real consumer exists. See this
service's [ADR-0003](adr/0003-consensus-result-stays-internal.md) for why, and
why it's additive to lift later (the raw outcome is already stored).

### Auth

JWT verification is copied, not imported, from the established widget pattern
(claims `sub`, `email`, `role`, `scope`, plus `stakeholder_role` here). The HTTP
routes are guarded as one group, authentication-only (`require_scopes([])` — a
valid monolith JWT, no particular scope; a dedicated `rounds:*` scope is out of
scope for this PRD). The WebSocket route self-guards instead (see above), and
`GET /rounds/widget.js` is the one deliberately unguarded route (a browser
`<script>` load carries no bearer token).

## Running it

```sh
make ui      # build the <round-widget> bundle into src/static/ (serves /rounds/widget.js)
make run     # uvicorn on :28005 with --reload
make test    # pytest (backend)
cd ui && npm test   # node --test (UI contract)
```

Env vars (`src/config/__init__.py`, pydantic-settings, `.env`-loadable):

- `JWT_ALGORITHM` (default `RS256`) / `JWT_VERIFICATION_KEY` — verify-only,
  mirrors the monolith's own env var names; this service holds no signing key and
  never issues tokens (system
  [ADR-0001](../../adr/0001-shared-database.md): one identity system, the
  monolith's). PEM values may be single-line with `\n` escapes.
- `DATABASE_URL` — the same shared Supabase the monolith reads (system ADR-0001).
- `REGISTER_IN_CATALOG` (default `true`) — toggles catalog self-registration on
  boot (see below).
- `NOTIFIER_PUBLISH_URL` (default
  `http://notification-service:28004/notifications/publish`) — the Realtime
  Notifier's publish ingress.

Dockerfile: two stages — `node:20-slim` builds the `<round-widget>` bundle
(`npm run build` → `round-widget.js`), then a `python:3.12-slim` FastAPI stage
copies it to `src/static/round-widget.js` (the path `GET /rounds/widget.js`
serves), drops to a non-root user, and listens on **28005** (its own dev port;
monolith 28000, demographic 28001, characteristic/reuse 28002, vocazione 28003,
notification 28004). Shares no code with the monolith — it copies its own `src/`.

Catalog self-registration: on boot the service best-effort upserts its own row
(`type = "rounds"`) into the shared `dashboards_config.widget_types` table,
pointing the monolith's generic `RemoteWidget` seam at `/rounds/widget.js` /
`<round-widget>` — no monolith code touched, and there's no in-app "Add widget"
menu to use instead. Never fatal: if the catalog table doesn't exist yet or the
DB role can't write the monolith's schema, it logs a warning and carries on. Set
`REGISTER_IN_CATALOG=false` and apply `catalog/widget-type.sql` by hand instead
when an operator must own that write.

Schema bring-up: `db/round-schema.sql` (the `public.round_outcomes` table +
grant) is applied by the compose `round-schema-init` one-shot on every bring-up,
not by the service at runtime — idempotent, loads no data.

Deploy: same pattern as every other widget — UI baked into the image (no dev
mount), so `docker compose build round-service && docker compose up -d
round-service` ships a change.

## Links out
- [Decision records](adr/)
- [Strangler-fig strategy](../../architecture/strangler-fig.md)
- [Full-stack Widget microservices](../../architecture/widget-microservice-fullstack.md)
- [Services overview](../README.md)
