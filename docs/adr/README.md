# Architecture Decision Records

System-wide decisions: one choice each, the options rejected, and why. A
service's own decisions (its data model, its own UI trade-offs) live on that
service's branch instead — see [Widget services](../services/README.md), each
with its own `adr/`.

- [0001 — Shared database](0001-shared-database.md): Widget services read/write
  the monolith's Supabase Postgres rather than owning a datastore.
- [0002 — Edge gateway, single front door](0002-edge-gateway-single-front-door.md):
  one dumb reverse proxy is the only origin the browser ever talks to.
- [0003 — Active Workshop selection bus](0003-active-workshop-selection-bus.md):
  the Active Workshop travels between widgets on a shared-`window` event bus.
- [0004 — Host pans the map on Active Workshop](0004-host-pans-map-on-active-workshop.md):
  one generic host listener pans every registered map, coupled only to the bus
  contract — not to any specific widget.
- [0005 — Generalize the selection bus](0005-generalize-selection-bus.md): the
  bus grows a per-axis contract (`praim:selection:<axis>`) so a second
  selection (Vocazione) doesn't need a second ad-hoc channel.
- [0006 — Page-global overlay seam](0006-page-global-overlay-seam.md): a second
  generic seam (`<RemoteOverlay>`) mounts chromeless, page-global widgets
  outside the card grid.

Back to [Architecture](../architecture/README.md).
