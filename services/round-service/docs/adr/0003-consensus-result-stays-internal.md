# The consensus result stays internal to the Round Manager — no cross-context Bene → Vocazione link yet

Status: accepted

When a Round reaches 100% **Consensus**, the Round Manager has, for the first time
in the system, a decided **(Bene → winning Vocazione)** fact. We keep that fact
**internal**: the Round Manager persists it in its own Round history (winner, number
of Rounds, timings, raw vote distributions) and shows it in the phase-4 recap, but
it does **not** write any link that other contexts (Building Characteristic,
Vocazione Selector, a future map layer) can consume.

The Vocazione context records as deliberate that there is **no stored
building→Vocazione link** ("a map layer that filters buildings by Vocazione has no
data to query yet"). A Round reaching consensus is the first thing that *could*
produce such a link — but exposing it now would move a boundary: the Round Manager
would become the owner of "this Bene is destined for this Vocazione," a fact the
Scheda and the Vocazione filter might then read and depend on. We decline that
coupling until a real consumer exists.

## Considered options

- **Keep the result internal (chosen).** Clean boundary; no context commits to a
  contract before there's a consumer. The raw outcome is still persisted, so
  exposing a link later is **additive, not destructive**.
- **Write a consumable Bene → Vocazione link** (shared-schema column or selection
  bus). Rejected for now: it realises the deferred map layer but couples Vocazione
  and Characteristic to the Round Manager's output speculatively, before anything
  consumes it.

## Consequences

- The deferred building→Vocazione map layer stays deferred; this widget does not
  unblock it yet.
- Because the raw outcome is stored (ADR-0002), promoting it to a cross-context link
  later is a forward-only change with no data migration.
