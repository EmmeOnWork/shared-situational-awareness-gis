# Widget services — context map

The Janus stack is being strangled into independent full-stack Widgets, each a
separate deployable that shares the monolith's Supabase database but never
edits the monolith's code. Each Widget owns its own language and, where noted,
its own UI. See the [strangler-fig strategy](../architecture/README.md) for why
the stack is shaped this way; this page is the bounded-context map — one entry
per service plus how they relate.

## Contexts

- [Demographic](demographic-service/README.md) — read-only data-source Widget
  serving aggregated ISTAT demographic data for a clicked Territory.
- [Building Characteristic](characteristic-service/README.md)
  (`characteristic-service`) — **write** Widget: lets a Workshop Master attach a
  building's blueprint photos and reuse data to a POI on the map. A **sensitive**
  widget: it shows whichever Bene is the **Active Workshop**.
- [Workshop Selector](reuse-service/README.md) (`reuse-service`) — owns the
  toggle-list of reuse POIs (Bene), pans the GIS map to the chosen one, and
  publishes the **Active Workshop** that sensitive widgets react to.
- [Vocazione Selector](vocazione-service/README.md) (`vocazione-service`) — a
  **stores-nothing** selector Widget: a dropdown of the 16 fixed **Vocazioni**
  (target reuse archetypes) that publishes the **Active Vocazione** page-globally
  so other widgets can re-scope. A *second* selection axis alongside the Active
  Workshop — *which kind of reuse*, not *which Bene*. Owns no tables and no data
  route.
- [Realtime Notifier](notification-service/README.md) (`notification-service`)
  — a **stateless / ephemeral** realtime Widget (prefix `/notifications`) that
  holds an authenticated WebSocket and renders self-describing Notifications
  (top-right toast + audio) pushed from the server. A generic *delivery
  surface*: it understands only **Severity** + an optional **Scope**, never a
  domain event type. Owns no tables.
- [Round Manager](round-service/README.md) (`round-service`; prefix `/rounds`)
  — the **first stateful, multi-user, realtime-shared** Widget: runs an
  iterative group **consensus process** over the current **Bene**, in which
  every **Participant** casts one final, secret **Vote** for a **Vocazione**
  each **Round**, deliberates anonymously in a per-Bene **Chat**, and the Round
  repeats until **Consensus** (1 − normalized Shannon entropy) reaches 100% and
  a winning Vocazione is decided. **Owns tables** (Participants, Roles, Rounds,
  Votes, Chat, raw outcome distributions + timings) and serves its own
  WebSocket with a per-Bene room. The server-side **producer** of round
  Notifications to the Realtime Notifier.
- [Scala Likert](likert-service/README.md) (`likert-service`; prefix `/likert`)
  — a read-mostly **gauge** Widget showing the **Gradimento**: how well-received
  the **Active Vocazione** is on the clicked comune, as the volume-weighted
  average of the online review stars of that Vocazione's **Competitors**. A
  *third consumer pairing* — *Active Vocazione × clicked comune* — that ignores
  the Active Workshop entirely. **Keeps its own cache** of external ratings
  (background-refreshed) — the first Widget to depend on an **external ratings
  provider**.
- [I Prezziari](prezzari-service/README.md) (`prezzari-service`; prefix
  `/prezzari`) — a **read-only, stores-a-snapshot** Widget showing two reference
  price lists side by side for reasoning about the **economic pre-feasibility of
  reusing** a building: the **Prezziario di Locazione** (Agenzia Entrate **OMI**
  rental quotations for the clicked comune) next to the **Prezzario dei Lavori**
  (a curated renovation slice of the **Regione Campania** price list). Comune-scoped,
  ignores the Active Workshop. **Owns tables** but holds static versioned
  snapshots, re-ingested manually with no runtime calls and no refresh worker.
- [Geo Layers](geo-layers-service/README.md) (`geo-layers-service`) — a
  **data-source Widget with no UI of its own**: serves GeoJSON map layers (rete
  fissa < 1 Gb markers; frana/idraulico/sismico ISPRA risk polygons) to the
  monolith's existing JuMap widget as **config data**
  (`additionalConfig.layers`), not a draggable card — so unlike every other
  Widget here it has no bundle, no custom element, and no catalog row.
  Comune-scoped (`region_id`) like the Scala Likert and I Prezziari; it ignores
  the Active Workshop.

## Relationships

- **Every service → Monolith (shared DB, [ADR-0001](../adr/0001-shared-database.md))**:
  every Widget reads the monolith's Supabase database directly, referencing the
  monolith's own entities (POIs, regions/areas, users/roles) **by id/name only**,
  never by geometry, and never importing monolith code.
- **Every service → Edge gateway ([ADR-0002](../adr/0002-edge-gateway-single-front-door.md))**:
  every Widget sits behind the gateway under its own URL prefix; a bundle
  (`/<prefix>/widget.js`), where one exists, is unguarded, and the data routes
  are JWT-guarded.
- **Demographic vs Building Characteristic**: Demographic only *reads* and
  speaks the read-only `DataResponse` contract. Building Characteristic
  *writes* (binary upload + authorized mutations) and does not reuse that
  contract.
- **Workshop Selector → sensitive widgets (Active Workshop)**: the Selector
  publishes the currently-selected Bene/POI; Building Characteristic (and any
  future sensitive widget) consumes it to know which Bene it is showing,
  depending only on the contract (an Active Workshop `poiId`), never on the
  Selector's internals. See [ADR-0003](../adr/0003-active-workshop-selection-bus.md)
  and [ADR-0004](../adr/0004-host-pans-map-on-active-workshop.md).
- **Realtime Notifier → all widgets (transport split)**: the Notifier is the
  first **server→many-clients** transport (WebSocket behind the gateway), distinct
  from the in-page **selection bus** ([ADR-0003](../adr/0003-active-workshop-selection-bus.md)/[0005](../adr/0005-generalize-selection-bus.md),
  one browser only). It carries generic Notifications (Severity + optional
  Scope); the Round Manager is the *producer* of round-derived Notifications.
  The Notifier reuses the selection bus only to *filter* a scoped Notification
  client-side against the receiver's Active Workshop — never as server-side
  rooms. See [ADR-0006](../adr/0006-page-global-overlay-seam.md).
- **Vocazione Selector → future consumers (Active Vocazione)**: the Selector
  publishes the chosen Vocazione on the generalized selection bus
  ([ADR-0005](../adr/0005-generalize-selection-bus.md): `praim:selection:<axis>`
  + retained `window.__praimSelections`), an independent axis alongside the
  Active Workshop. There is no stored building→Vocazione link, so a map layer
  filtering buildings by Vocazione is deferred. Touches the Building
  Characteristic context only to relabel its Scheda `destinazione_uso` as
  "(attuale)".
- **Round Manager → Realtime Notifier (producer)**: the Round Manager's backend
  POSTs round-lifecycle Notifications (round closed `info`, new round `info`,
  consensus reached `success`), each carrying the Bene's Scope, to the
  Notifier's publish ingress. A Vote carries no Notification (local widget
  feedback only).
- **Round Manager → Workshop Selector (Active Workshop, sensitive consumer)**:
  the Round Manager *consumes* the Active Workshop to know which Bene's Round
  to show; every per-Bene thing (WebSocket room, roster, Chat, Round history)
  keys off it. No Active Workshop ⇒ empty state.
- **Round Manager → Vocazione catalog (votes-on, no stored link)**: a Vote
  picks from the same 16-Vocazione catalog the Vocazione Selector owns, but is
  a private ballot, not the Active Vocazione. At 100% Consensus the winning
  Vocazione stays **internal** to the Round Manager — it does not write the
  deferred Bene→Vocazione link.
- **Scala Likert → Vocazione Selector + Concorrenza bridge**: consumes the
  Active Vocazione off the selection bus and reuses the monolith's
  Vocazione→Competitor mapping (the `vocazione_competitors` prefix map + the
  comune-scoped POI join the Concorrenza map layer uses) to know which POIs'
  stars to average — copying the mapping per the strangler pattern, never
  importing monolith code.
- **Scala Likert → Monolith (shared DB + clicked point)**: receives the clicked
  point as host-set `lat`/`lng` (like the Demographic Widget) and resolves it to
  a comune itself; reads POIs/areas by id/name only. Comune-grained, unlike the
  province-grained Demographic Widget.
- **Scala Likert → external ratings provider**: the Gradimento's raw material
  is online review stars sourced from an external provider, kept in the
  Widget's own cache (background-refreshed) — the first external-data
  dependency in the stack.
- **I Prezziari → Monolith (shared DB + clicked point)**: receives the clicked
  point as host-set `lat`/`lng` and resolves it to a comune itself, exactly like
  the Scala Likert. It does **not** consume the Active Workshop — two Beni in
  the same comune see the same figures, so geography, not the Bene, is the
  axis. Only the OMI (Lista A) reacts to the click; the Campania prezzario
  (Lista B) is region-fixed.
- **I Prezziari → source publications (owns static snapshot tables)**: like the
  Scala Likert it owns tables, but the data is static, versioned, re-derivable
  reference material (OMI semestral, Campania prezzario annual), ingested
  offline with no runtime calls, no TTL and no refresh worker. Latest edition
  only; Campania-only OMI.
- **Geo Layers → Monolith (JuMap config, no catalog row)**: the only Widget
  that is pure map-layer data — it plugs into the monolith's existing JuMap
  renderer via a config entry (`useGeoJSONFetchPath`), not the `remote` seam, so
  it needs neither a bundle nor a `dashboards_config.widget_types` row.
  Comune-scoped like I Prezziari and the Scala Likert; it never reads or reacts
  to the Active Workshop.

## System-wide decisions

System-wide ADRs live in [`docs/adr/`](../adr/README.md); each service's own
decisions live under its own branch (e.g. [`round-service/adr/`](round-service/README.md)).
