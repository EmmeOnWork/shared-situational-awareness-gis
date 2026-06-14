# The host pans the GIS map on the Active Workshop bus, generically

When a Bene becomes the **Active Workshop** (published on the
`praim:workshop-selected` bus, ADR-0003), the dashboard should pan/centre its
Leaflet/GIS map on that Bene so the user sees where it is. ADR-0003 already
assigned "moving the GIS map" to the **host**, not to each sensitive widget. The
open question (reuse-service PRD, Slice 4) was *how* to wire it without coupling
the monolith to the Selector or to any particular widget.

We add a **single generic host listener** — the `useWorkshopMapPan` hook
(`components/widgets/JuMap/hooks/useWorkshopMapPan.ts`), installed once at the
dashboard page. On `praim:workshop-selected` it reads `detail.lat/lng` and pans
**every map registered in `mapStore`** via `MapWrapper.setCenterAndZoom`. It also
converges on the retained `window.__praimActiveWorkshop` at install, mirroring the
bus's late-join semantics (ADR-0003). The host couples only to the bus contract
(the event name + coordinates); it knows nothing about reuse-service, the
Selector, or any widget.

Late-join is extended to the **map**, not only to listeners. On a reload the
Selector restores the Active Workshop asynchronously (it fetches its Bene list,
then re-publishes from the URL param), and the GIS map registers asynchronously
too. A map that registers *after* the selection was published is not reached by
the one-shot event — unlike the area filter, which is durable store state and
converges for free (ADR-0003). So the hook also subscribes to `mapStore` and pans
each newly-registered map to the retained workshop, so the centring converges
whichever way the race between the Selector's restore and the map's init resolves.

## Considered options

- **Per-widget host code** (e.g. the monolith importing the Selector or a
  `reuse`-specific handler). Rejected: it re-couples the monolith to a remote
  widget, the exact thing the micro-frontend seam and ADR-0003 avoid.
- **Pan from the reuse-service bundle** (the widget reaches into the monolith's
  `mapStore`). Rejected: widgets never touch the monolith — they speak only their
  own service through the gateway. The bundle owns publishing the Active Workshop,
  not driving host chrome.
- **A thin host helper the widget calls back into.** Rejected for v1: it needs the
  host to hand the bundle a callback (more wiring) to achieve the same effect one
  generic listener already gives for free.

## Consequences

- New widgets that publish an Active Workshop pan the map with no extra host
  code; the listener is generic to the bus, not to the Selector.
- Panning is centralised in one hook, keyed off `mapStore`, so it covers however
  many maps a dashboard registers (one today) and stays out of every sensitive
  widget's scope.
- The glue is **host-coupled to Leaflet and verified manually** — no automated
  test, per the reuse-service PRD's Testing Decisions. The testable contract (the
  publisher) is already covered in reuse-service's `active-workshop.test.ts`.
- Centre zoom is a fixed building-scale default (16); making it configurable is
  deferred until a dashboard needs it.
