# Active Workshop selection travels on a shared-`window` event bus

A **Workshop Selector** widget needs to tell other ("sensitive") widgets — the
first being `building_characteristic` — which reuse POI (Bene) is currently under
consideration (the **Active Workshop**). We broadcast it as a browser
`CustomEvent` (`praim:workshop-selected`, `detail: { poiId, lat, lng, name }`) on
the host's `window`, plus a retained last value (`window.__praimActiveWorkshop`)
read at mount so late-joining/HMR-remounted widgets converge. Sensitive widgets
subscribe; they depend only on the contract (an Active Workshop `poiId`), never on
the Selector. This works because all Widget bundles share the host's JS realm —
Shadow DOM isolates style and markup, not `window` — the same insight already
recorded for the auth fetch interceptor in `docs/idea-futura.md`.

## Considered options

- **Host `dashboardStore` + a new generic `poi-id` host→element attribute** (the
  way the coarser `area` filter already flows). Rejected for v1: it is a monolith
  edit on the generic seam, and a remote bundle (the Selector) cannot write the
  host store without a host-provided callback. Kept as a possible future
  hardening if the selection must become inspectable dashboard state.
- **`BroadcastChannel`**: rejected — cross-tab scope we do not need; the widgets
  live in one page.

## Consequences

- No monolith code change to wire selection between widgets; new sensitive widgets
  inherit the channel for free by subscribing.
- The Active Workshop survives a page reload; **persisting** it (URL param
  recommended, so a Bene's dashboard is shareable) and **moving the GIS map** are
  the Selector's/host's responsibility, out of each sensitive widget's scope.
- The channel is global to the page: a single Active Workshop at a time. If two
  independent selections were ever needed on one page, this would need namespacing.
