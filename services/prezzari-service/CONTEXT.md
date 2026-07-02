# I Prezziari Widget (PRAIM)

A read-only Widget service (`prezzari-service`, gateway prefix `/prezzari`) that shows
**two reference price lists side by side** to support reasoning about the economic
**pre-feasibility of reusing** a building. Left pan: the **market rent** of the clicked
comune (the OMI rental quotations). Right pan: the **cost of building works** (a curated
slice of the Regione Campania public-works price list). It reads its **own tables**
(versioned snapshots of both lists) and never calls the source sites at runtime; it never
edits the monolith. It is **comune-scoped on the clicked point** like the Demographic and
Scala Likert Widgets — it does **not** consume the Active Workshop.

## Language

### Prezziari domain

**I Prezziari**:
The Widget itself — **two reference price lists rendered next to each other**, never merged
or summed. It is a **consultation surface**, not a calculator: it presents raw published
figures and lets the user weigh them by eye. The "balance" between the two pans (what reuse
*earns* vs what the works *cost*) is the **human reading**, not a number the Widget produces.
It reacts to **one** input — the **clicked comune** — and only the left list changes with it;
the right list is region-fixed.
_Avoid_: preventivo / computo metrico (no quantities, no totals), bilancia as if it were a
computed metric, calcolatore di convenienza.

**Prezziario di Locazione (Lista A)** *(sourced from the Agenzia delle Entrate OMI)*:
The left list — the **OMI rental quotations** for the clicked comune: for each **Zona OMI**
× building typology × conservation state, the **min–max canone** in €/m²/month. It is the
**market-rent** pan: how much that location lets for. Only the **locazione** values are kept;
the OMI sale (compravendita) values are deliberately dropped, because reuse keeps and lets the
Bene rather than selling it. Shown at **comune** granularity — **all** the comune's Zone OMI
as rows, not resolved to the single zona under the clicked point.
_Avoid_: compravendita / valore di mercato di vendita (out of scope), "gestione" (no referent
in OMI — the term is dropped), a single value (it is a list of zones).

**Zona OMI**:
The OMI micro-zone within a comune (e.g. `B1`, `C2`, `D3`) that the rental quotation is keyed
to — a comune has several. The Widget lists every Zona OMI of the comune; it does **not** map
the clicked lat/lng to one specific zona (that would need the OMI zone geometries, out of
scope).

**Prezzario dei Lavori (Lista B)** *(sourced from the Prezzario Regione Campania)*:
The right list — a **curated slice** of the Regione Campania public-works price list, limited
to the **building renovation / recovery** chapters (not roads, aqueducts, etc.). Each **Voce**
carries its **codice, descrizione, unità di misura and prezzo unitario**. It is the
**works-cost** pan. It is **region-wide**: identical everywhere in Campania, so it does **not**
change with the clicked comune. Navigable by **Capitolo** with a text search over the
descriptions.
_Avoid_: prezzario intero (the non-building chapters are excluded), a comune-specific list (it
is regional and click-independent).

**Voce / Capitolo**:
A **Voce** is one priced line of the Prezzario dei Lavori (codice + descrizione + unità di
misura + prezzo unitario); a **Capitolo** is the chapter that groups them (e.g. `A03`). The
Widget shows only the Capitoli of the curated renovation slice.

**Pubblicazione**:
The dated edition of each source list — OMI is published **semestrally**, the Campania prezzario
**annually** (the current one is 2026). The Widget stores each snapshot with its publication
label but **shows only the latest** of each; there is **no historical comparison**. When a new
edition appears the snapshot is re-ingested (an implementation concern — see this context's ADR
— not domain language).

### Inherited / referenced

**comune** *(the clicked Territory; owned by the monolith's geography)*:
The administrative unit the Lista A is computed for — a monolith **region**
(`area_type_id = 3`) resolved from the map click, delivered as the host-set `lat`/`lng` of the
click (the same point every Widget receives) and resolved to its region by the Widget itself,
exactly as the Scala Likert does. The OMI rows are scoped to this comune; the Lista B ignores it.

**POI / Bene**:
A POI is the monolith's point of interest; a **Bene** is the confiscated/public building (a
special POI). Like the Scala Likert and unlike the Building Characteristic or Round Manager, I
Prezziari is **not** a sensitive widget — it does **not** consume the **Active Workshop** and
shows nothing keyed to a specific Bene. Two Beni in the same comune see the same figures, so the
geography, not the Bene, is the axis.

## Flagged ambiguities

- **"Bilancia" / pre-feasibility is a framing, not a metric.** The Widget computes **nothing**
  and merges nothing: it presents two raw published lists and the user draws the conclusion. No
  totals, no break-even, no quantity selection. The two pans even carry incompatible units
  (€/m²/month vs €/unit-of-work), which is exactly why no automatic formula is offered.
- **"Gestione e locazione" reduced to locazione.** The OMI has no "gestione" category; only the
  locazione (rental) values are kept, and compravendita is dropped on purpose.
- **Asymmetric reaction to the click.** Lista A (OMI) updates with the clicked comune; Lista B
  (Campania prezzario) is region-fixed and stands still. This is intended, not a bug.
- **Comune-grained, not zona-OMI-grained.** Lista A lists all the comune's Zone OMI rather than
  resolving the click to one zona, to avoid depending on OMI zone geometries.
- **Static reference data, not live.** Both lists are slow-moving published snapshots (semestral /
  annual), held in the Widget's own tables and re-ingested manually; the Widget never calls the
  source sites at runtime — unlike the Scala Likert's background-refreshed external provider.
- **Campania-only OMI snapshot.** Although the OMI is national, only the Campania comuni are
  ingested, to match the region-bound Lista B and the Campania-bound map. A click outside Campania
  resolves to no comune (neutral initial state).
- **The two lists degrade independently.** A missing left list does not blank the right one and
  vice versa: a comune with no published OMI shows "quotazioni OMI non disponibili per questo
  comune" on the left while the regional Lista B stays visible. The two pans are independent
  surfaces that happen to share a panel.

## Example dialogue

> **Dev:** The user clicked Avellino. What do the two lists show?
> **Domain:** Left, every Zona OMI of Avellino with its min–max rental canone in €/m²/month —
> the market-rent pan. Right, the curated renovation Capitoli of the Campania 2026 prezzario with
> their voci and unit prices — the works-cost pan. The right list would be the same if they'd
> clicked any other Campania comune.
> **Dev:** Can I sum the works I need and compare it to the rent?
> **Domain:** Not in the Widget — it does no maths. It shows the raw figures; you do the weighing
> yourself. It's a consultation surface, not a preventivo.
> **Dev:** Does selecting a Bene (Active Workshop) change it?
> **Domain:** No. I Prezziari keys off the clicked comune only, like the Scala Likert. The Bene
> axis is ignored.
> **Dev:** Do I see last semester's OMI too, to compare?
> **Domain:** No — only the latest publication of each list. No historical comparison.
