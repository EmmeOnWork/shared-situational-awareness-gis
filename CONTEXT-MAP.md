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

## System-wide decisions

System-wide ADRs live in [`docs/adr/`](./docs/adr/); context-specific ADRs live
under each service's own `docs/adr/`.
