# Generalize the selection bus to multiple axes (per-axis namespaced events)

ADR-0003 introduced a single page-global `window` bus for the Active Workshop
(`praim:workshop-selected` + `window.__praimActiveWorkshop`) and flagged that a
second independent selection "would need namespacing." The **Vocazione Selector**
(`vocazione-service`) is that second axis. We generalize the bus to a **per-axis
contract**: events `praim:selection:<axis>` carrying the axis object (or `null` when
cleared), a retained map `window.__praimSelections[axis]`, behind small
`publishSelection(axis, value)` / `subscribeSelection(axis, fn)` / `readSelection(axis)`
helpers — re-implemented as a copied helper in each independent deployable (no shared
package), consistent with the strangler architecture.

**Phased migration (deliberate).** `vocazione-service` adopts this contract from day
one. The existing workshop copies — the reuse-service publisher, the
characteristic-service subscriber, the host `useWorkshopMapPan` hook, and their two
tests — keep the legacy `praim:workshop-selected` shape and migrate to the generalized
contract in a **separate, focused change**. Two conventions therefore coexist until
that migration lands. Accepted because the Vocazione widget has no consumer to
coordinate with yet (its map layer and other consumers are deferred), so the unify-the-
workshop-bus refactor is pure tidiness on working code and need not block shipping.

## Considered options

- **A parallel ad-hoc bus per axis** (`praim:vocazione-selected`, a sibling of the
  workshop event). Rejected: a 3rd axis would mean a 3rd bus; ADR-0003 already pointed
  at namespacing.
- **One discriminated event** (`praim:selection-changed` with `detail: {axis, value}`).
  Rejected: forces every consumer to filter by `axis` (boilerplate + a footgun if
  forgotten); per-axis event names let a consumer subscribe to exactly its axis.
- **A shared bus package** imported by all services. Rejected: couples independent
  deployables' builds/versions, against "each Widget owns its own"; the established
  pattern is a copied helper (characteristic copied reuse's file).
- **Full migration of the workshop bus in the same change.** Rejected for now: large
  blast radius across reuse + characteristic + monolith for no functional gain; phased
  instead.

## Consequences

- Two bus conventions coexist until the workshop migration; the Active Workshop is
  unaffected meanwhile.
- New selection axes become cheap and uniform: one `publishSelection(axis, …)` call
  plus the retained map; late-joiners `readSelection(axis)` at mount.
- The retained value moves from a single `__praimActiveWorkshop` to a per-axis
  `__praimSelections` map; the workshop migration must preserve ADR-0003/0004 late-join
  semantics (read retained at mount; the host hook also pans maps that register late).
- `null` is the explicit **cleared** value (Vocazione's "Tutte"); the workshop axis
  simply never clears.
