# Demographic Microservice (PRAIM)

A standalone backend service that serves aggregated ISTAT demographic data as a
dashboard data-source ("widget"). It shares the Janus monolith's Supabase
database but is a separate deployable and never modifies the monolith's code.

## Language

### Demographic domain

**Territory**:
A named administrative unit that demographic data is reported for. Has a
**level**: `province`, `region`, `macro-area`, or `national`. The name is the
join key the widget filters on. The canonical name is the full official Italian
form (e.g. `Friuli-Venezia Giulia`); the raw ISTAT label (e.g. `Friuli-V. G.`)
is retained alongside for traceability.
_Avoid_: country, zone, region (when you mean the national or macro level)

**Level**:
The rung of the Italian administrative hierarchy a Territory sits on —
`province` (106) ⊂ `region` (20) ⊂ `macro-area` (5) ⊂ `national` (1). ISTAT
publishes pre-aggregated values at every level; the service never rolls one
level up into another.

**Demographic profile**:
The full set of indicators returned for one Territory: population by
citizenship, age structure, and migration. Assembled by integrating ISTAT
Tables 1 and 4 on the Territory name.

**Population by citizenship**:
Resident headcount split into **Italian**, **foreign**, and **total**, in
**thousands** as ISTAT publishes it. A *stock* — how many people reside there.
_Avoid_: immigrants (for the foreign count — that conflates stock with flow)

**Age structure**:
The share (%) of residents in each broad age class: `0–14`, `15–64`, `65+`.

**Migration rate**:
Net moves per 1,000 residents in a year — **internal**, **foreign**, and
**total**. A *flow*. Distinct from the foreign **population** count, which is a
stock; do not merge the two under "immigration".

**Selection layer**:
The (not-yet-built) map feature that turns one map click into the parameters
each widget needs. It owns geographic resolution: mapping a finer clicked shape
(e.g. comune `Monteverde`) to the nearest Territory that has data (province
`Avellino`), and labelling the result an estimate. The demographic service does
no geometry and trusts the layer to send a valid Territory name.

**Estimate (parent-inherited)**:
A value shown for a finer unit that has no ISTAT row, taken from its containing
Territory. Only intensive indicators (age shares, migration rates) inherit
honestly; absolute population counts do not. The service surfaces the Territory
and level it actually answered for, so the caller can label estimates truthfully.

### Inherited from the monolith

**Widget**:
A backend data-source domain that returns the data a dashboard panel renders —
server-side only. The demographic widget is one, alongside `pollution` and
`weather`.
_Avoid_: component, panel (frontend concerns)

**DataResponse**:
The canonical response contract reused from the monolith: a `label`, a `data`
map of key→value, an optional datetime range (null here — demographics are not a
time series), and `metadata`. The demographic widget puts indicator→value pairs
in `data` and context (level, units, reference periods, quality flags, answered
Territory) in `metadata`.

**Region / Area / Area Type**:
The monolith's own geography (`regions` with `admin_type`, `areas` with `geom`
and an `area_type_id`). The demographic service references these by **name**
only and never reads their geometry. A future `territory_name → regions`
foreign key is anticipated but deliberately not built yet.

## Flagged ambiguities

- **"Country"** — the user's original word for an entry in the ISTAT
  `Province / Regioni / Ripartizioni` column. Resolved to **Territory** + level;
  "country" is reserved for nations and is avoided.
- **"Immigration"** — splits into the foreign **Population by citizenship**
  (stock) and the foreign **Migration rate** (flow). Always name which.

## Example dialogue

> **Dev:** A user clicked Monteverde. What does the widget return?
> **Domain:** Monteverde is a comune — no ISTAT row. The selection layer
> resolves it to its province, Avellino, and asks us for `territory=Avellino`.
> **Dev:** So we return Avellino's numbers?
> **Domain:** Yes — the real ones. We put `level: province` and
> `territory_name: Avellino` in the metadata so the UI can say "province-level
> estimate." We never invent a Monteverde figure.
> **Dev:** And if someone asks us for `Monteverde` directly?
> **Domain:** 404. Resolution isn't our job — a name we don't have is an error,
> not empty data.
