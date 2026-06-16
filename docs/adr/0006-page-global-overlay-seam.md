# Page-global overlay Widgets mount via a second generic seam

The micro-frontend doctrine so far is *one* generic monolith edit — the `remote`
card seam ([widget-microservice-fullstack](../architecture/widget-microservice-fullstack.md))
— after which every Widget is added as catalog data and the monolith is never
touched again. The **Realtime Notifier** (`notification-service`) breaks the
assumption that seam encodes: it must render **chromeless, page-global** toasts
(viewport top-right) plus an audio alert, **invisible until a notification
arrives**. The `remote` seam mounts every Widget inside a `DraggableWidget` card
(title bar, border, remove button) in the `EditableLayout` grid; a Widget cannot
hide its own card frame (it is host DOM outside the element's shadow root), and a
card is present only if a user added it to the layout. A notification overlay is
genuinely **not a card**.

We therefore accept a **second generic seam** in the dashboard shell: a one-time,
widget-agnostic `<RemoteOverlay>` mounted once in
[`layout.tsx`](../../monolith/frontend/src/app/dashboard/layout.tsx) that loads
**chromeless, page-global** remote bundles listed **declaratively** (data-driven —
e.g. catalog rows flagged `placement: "overlay"` instead of `"grid"`). It names no
widget, carries the same host→element contract as `remote` (`token`/`base`), and is
the **last** overlay-related monolith edit: a future overlay Widget self-registers
as an overlay and appears with no further code change — exactly as `remote` made
itself the last *card* edit. The doctrine becomes "**two** generic seams (grid +
overlay), never a per-widget edit," not "one seam forever."

## Considered options

- **Mount the Notifier as a normal card Widget.** Rejected: `DraggableWidget`
  draws unavoidable card chrome around every grid slot, the element cannot suppress
  its own frame, and a card exists only when added to a layout and occupies a grid
  cell for something that is invisible most of the time — all against the stated
  requirement (chromeless, always-present, top-right of the viewport).
- **A per-widget shell edit** (`case "notifications"` in the shell, or importing
  the Notifier). Rejected: re-couples the monolith to a specific Widget, the exact
  thing the `remote` seam and the strangler strategy exist to prevent. The seam
  stays generic precisely so widget N+1 reuses it unchanged.
- **No monolith edit at all.** Rejected as impossible without relaxing the
  chromeless/page-global requirement: there is no existing non-grid mount point, and
  a bundle mounted in a card cannot escape that card's chrome.

## Consequences

- A second generic seam now exists; the invariant "the monolith is edited once"
  becomes "the monolith carries two generic seams (grid `remote` + page-global
  overlay), and still never a per-widget `case`." Adding a *third* kind of seam
  should clear the same bar this one did.
- Overlays are **page-global**, not bound to a dashboard card. Scoping a
  Notification to a particular **Bene** is therefore a **client-side filter** against
  the selection bus (ADR-0003/0005: render only if the Notification's `scope` matches
  the receiver's Active Workshop), never server-side rooms and never placement.
- The overlay element receives the same `token`/`base` the host already refreshes
  for card Widgets, so the WS connection authenticates with the monolith JWT
  (gateway realtime convention, ADR-0002) with no new host machinery.
- Audio autoplay needs no visible control: the Notifier resumes its `AudioContext`
  on the first page-wide user gesture, consistent with "invisible until a toast."
