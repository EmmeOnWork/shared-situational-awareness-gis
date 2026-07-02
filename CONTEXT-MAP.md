# Context Map

The Janus stack is being strangled into independent full-stack Widgets, each a
separate deployable that shares the monolith's Supabase database but never edits
the monolith's code. Each Widget owns its own language.

## Contexts

- [Demographic](./services/demographic-service/CONTEXT.md) — read-only data-source
  Widget serving aggregated ISTAT demographic data for a clicked Territory.
- [Building Characteristic](./services/characteristic-service/CONTEXT.md)
  — **write** Widget (`characteristic-service`): lets a Workshop Master attach a
  building's blueprint photos and reuse data to a POI on the map. A **sensitive**
  widget: it shows whichever Bene is the **Active Workshop**.
- **Workshop Selector** (`reuse-service`; built first, design deferred) — owns the
  toggle-list of reuse POIs (Bene), pans the GIS map to the chosen one, and
  publishes the **Active Workshop** that sensitive widgets react to. It is the
  POI-granular realisation of the "Selection layer" the Demographic context
  anticipated but left unbuilt.
- [Vocazione Selector](./services/vocazione-service/CONTEXT.md) (`vocazione-service`)
  — a **stores-nothing** selector Widget: a dropdown of the 16 fixed **Vocazioni**
  (target reuse archetypes) that publishes the **Active Vocazione** page-globally so
  a future map layer and other widgets can re-scope. A *second* selection axis
  alongside the Active Workshop — *which kind of reuse*, not *which Bene*. Owns no
  tables and no data route.
- [Realtime Notifier](./services/notification-service/CONTEXT.md) (`notification-service`;
  *in design*) — a **stateless / ephemeral** realtime Widget (prefix `/notifications`)
  that holds an authenticated WebSocket and renders **self-describing Notifications**
  (top-right toast + audio) pushed from the server. It is a generic *delivery surface*:
  it understands only **Severity** + an optional **Scope**, never a domain event type.
  The **Round** logic that produces these Notifications is a separate widget
  ([Round Manager](./services/round-service/CONTEXT.md), now in design). Owns no tables.
- [Round Manager](./services/round-service/CONTEXT.md) (`round-service`; prefix
  `/rounds`, *in design*) — the **first stateful, multi-user, realtime-shared** Widget:
  it runs an iterative group **consensus process** over the current **Bene**, in which
  every **Participant** casts one final, secret **Vote** for a **Vocazione** each
  **Round**, deliberates anonymously in a per-Bene **Chat**, and the Round repeats until
  **Consensus** (1 − normalized Shannon entropy) reaches 100% and a **winning Vocazione**
  is decided. **Owns tables** (Participants, Roles, Rounds, Votes, Chat, raw outcome
  distributions + timings) — unlike every prior Widget. Serves its **own WebSocket with
  a per-Bene room** for live state, and is the server-side **producer** of round
  Notifications to the Realtime Notifier.
- [Scala Likert](./services/likert-service/CONTEXT.md) (`likert-service`; prefix
  `/likert`, *in design*) — a read-mostly **gauge** Widget that shows the **Gradimento**:
  how well-received the **Active Vocazione** is on the **clicked comune**, as the
  volume-weighted average of the online review stars of that Vocazione's **Competitors**
  (the same set the Concorrenza map layer paints). A **third consumer pairing** —
  *Active Vocazione × clicked comune* — distinct from the sensitive *Active Workshop*
  widgets; it ignores the Active Workshop entirely. **Keeps its own cache** of the
  external ratings (background-refreshed) — the second Widget to own tables and the
  first to depend on an **external ratings provider** — but never edits the monolith.
- [I Prezziari](./services/prezzari-service/CONTEXT.md) (`prezzari-service`; prefix
  `/prezzari`, *in design*) — a **read-only, stores-a-snapshot** Widget that shows **two
  reference price lists side by side** to support reasoning about the **economic
  pre-feasibility of reusing** a building: the **Prezziario di Locazione** (Agenzia
  Entrate **OMI** rental quotations for the clicked comune — the market-rent pan) next to
  the **Prezzario dei Lavori** (a curated renovation slice of the **Regione Campania**
  price list — the works-cost pan). A **comune-scoped** consumer of the clicked point
  (like the Scala Likert), it **ignores the Active Workshop**. The "balance" between the
  pans is the **human reading**, not a computed metric — the Widget does **no maths** and
  merges nothing. **Owns tables** but holds **static versioned snapshots** (latest edition
  only, Campania-only), re-ingested manually with **no runtime calls** to the source sites
  and **no refresh worker / TTL** — unlike the Scala Likert's background-refreshed provider.

## Relationships

- **Both → Monolith (shared DB, ADR-0001)**: every Widget reads the monolith's
  Supabase database directly, referencing the monolith's own entities (POIs,
  regions/areas, users/roles) **by id/name only**, never by geometry, and never
  importing monolith code.
- **Both → Edge gateway (ADR-0002)**: every Widget sits behind the gateway under
  its own URL prefix; the bundle (`/<prefix>/widget.js`) is unguarded, the data
  routes are JWT-guarded.
- **Demographic vs Building Characteristic**: Demographic only *reads* and speaks
  the read-only `DataResponse` contract. Building Characteristic *writes* (binary
  upload + authorized mutations) and does **not** reuse that contract.
- **Workshop Selector → sensitive widgets (Active Workshop)**: the Selector
  publishes the currently-selected Bene/POI; Building Characteristic (and any
  future sensitive widget) consumes it to know which Bene it is showing. The
  transport mechanism is being decided (see the Building Characteristic context);
  Building Characteristic depends only on *the contract* (an Active Workshop
  `poiId`), never on the Selector's internals.
- **Realtime Notifier → all widgets (transport split)**: the Notifier is the first
  **server→many-clients** transport (WebSocket behind the gateway, ADR-0002's realtime
  auth convention), distinct from the in-page **selection bus** (ADR-0003/0005, one
  browser only). It carries generic **Notifications** (Severity + optional Scope); the
  future **Round Manager** is the *producer* of round-derived Notifications. The Notifier
  reuses the selection bus only to *filter* a scoped Notification client-side against the
  receiver's **Active Workshop** — never as server-side rooms.
- **Vocazione Selector → future consumers (Active Vocazione)**: the Selector
  publishes the chosen **Vocazione** on the **generalized selection bus** (ADR-0005:
  `praim:selection:<axis>` + retained `window.__praimSelections`), as an independent
  axis alongside the Active Workshop — realising the "two independent selections"
  case ADR-0003 anticipated. The Vocazione axis ships on this contract now; the
  Workshop axis migrates to it in a later, separate change (two conventions coexist
  meanwhile). There is **no stored building→Vocazione link**, so the map layer that
  would filter buildings by Vocazione is deferred; the Selector only guarantees a
  consumable broadcast. Touches the Building Characteristic context only to relabel
  its Scheda `destinazione_uso` as "(attuale)".
- **Round Manager → Realtime Notifier (producer)**: the Round Manager's backend is the
  automated *producer* the Notifier context anticipated — it POSTs round-lifecycle
  Notifications (round closed `info`, new round `info`, consensus reached `success`),
  each carrying the Bene's **Scope**, to the Notifier's publish ingress. A Vote carries
  no Notification (local widget feedback only).
- **Round Manager → Workshop Selector (Active Workshop, sensitive consumer)**: the Round
  Manager *consumes* the Active Workshop to know which Bene's Round to show; every
  per-Bene thing (WebSocket room, roster, Chat, Round history) keys off it. No Active
  Workshop ⇒ empty state.
- **Round Manager → Vocazione catalog (votes-on, no stored link)**: a **Vote** picks from
  the same 16-Vocazione catalog the Vocazione Selector owns, but is a private ballot, not
  the Active Vocazione. At 100% Consensus the **winning Vocazione** is kept **internal**
  to the Round Manager (its own context ADR-0003) — it does **not** write the deferred
  Bene→Vocazione link, leaving that boundary unchanged.
- **Round Manager → Monolith (owns tables, a departure)**: unlike every prior Widget
  (stores-nothing or single-client read/write), the Round Manager is **stateful,
  multi-user and realtime-shared** and **owns tables** in the shared `public` schema
  (Participants, Roles, Rounds, Votes, Chat, raw outcome distributions + timings). It
  runs its **own per-Bene WebSocket** (its own context ADR-0001), the first server-side
  shared mutable state in the stack — distinct from the Notifier's roomless broadcast.
- **Scala Likert → Vocazione Selector + Concorrenza bridge**: consumes the **Active
  Vocazione** off the selection bus and reuses the monolith's Vocazione→Competitor
  mapping (the `vocazione_competitors` prefix map + the comune-scoped POI join the
  Concorrenza layer uses) to know *which* POIs' stars to average. It reads that competitor
  set from the shared DB, copying the mapping per the strangler pattern, never importing
  monolith code.
- **Scala Likert → Monolith (shared DB + clicked point)**: receives the clicked point as
  host-set `lat`/`lng` (like the demographic Widget) and resolves it to a **comune
  (region)** itself; reads POIs/areas by id/name only. Distinct from the demographic
  Widget, which answers province-level — the Scala Likert is comune-grained.
- **Scala Likert → external ratings provider (a departure)**: unlike every prior
  read-side Widget, the Gradimento's raw material is **online review stars** sourced from
  an external provider and kept in the Widget's **own cache** (background-refreshed) — the
  first external-data dependency in the stack, recorded in the context's ADR.
- **I Prezziari → Monolith (shared DB + clicked point)**: receives the clicked point as
  host-set `lat`/`lng` and resolves it to a **comune (region)** itself, exactly like the
  Scala Likert; it reads the monolith's geography by id/name only. It **does not consume
  the Active Workshop** — two Beni in the same comune see the same figures, so geography,
  not the Bene, is the axis. Only the OMI (Lista A) reacts to the click; the Campania
  prezzario (Lista B) is region-fixed.
- **I Prezziari → source publications (owns static snapshot tables)**: like the Scala
  Likert it **owns tables**, but unlike it the data is **static, versioned, re-derivable**
  reference material (OMI semestral, Campania prezzario annual), ingested **offline** and
  read with **no runtime calls, no TTL and no refresh worker**. It is the first Widget to
  own tables whose contents are published editions rather than a live/drifting signal —
  recorded in the context's ADR. Latest edition only; Campania-only OMI.

## System-wide decisions

System-wide ADRs live in [`docs/adr/`](./docs/adr/); context-specific ADRs live
under each service's own `docs/adr/`.
