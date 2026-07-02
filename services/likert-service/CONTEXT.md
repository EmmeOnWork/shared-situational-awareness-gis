# Scala Likert Widget (PRAIM)

A read-mostly Widget service (`likert-service`, gateway prefix `/likert`) that shows,
on a single red→green gauge, **how well-received the Active Vocazione is on the
clicked comune** — its **Gradimento** — read from the online review stars of that
Vocazione's market **Competitors** already on the map. It reads the shared Janus
database for the competitor set and consumes the **Active Vocazione** off the
selection bus; it never edits the monolith. Unlike the stores-nothing selectors it
keeps its **own cache** of the external ratings (how, and from where, is an
implementation concern — see this context's ADR — not domain language).

## Language

### Likert domain

**Scala Likert**:
The widget itself — a single horizontal **gauge** from red (left) through yellow to
green (right) with a **needle** at the current **Gradimento**, plus an **emoji** that
names the level at a glance. Despite the name it is a continuous rating *gauge*, not a
survey Likert scale (the discrete agree/disagree instrument); the name is kept by
product choice. It reacts to **two** inputs at once — the **Active Vocazione** and the
**clicked comune** — and shows nothing until both are present. Opening it reveals the
evidence behind the position (the Gradimento breakdown).
_Avoid_: Likert scale (in the psychometric sense — this is a gauge), sentiment meter
(sentiment is a different, ABSA notion), thermometer.

**Gradimento**:
The level the needle points at: **how well-received the Active Vocazione is on the
clicked comune**, taken as the volume-weighted average of the **online star-ratings**
(1–5) of that Vocazione's **Competitor** POIs located in that comune — each public
review counting once, so a busier competitor weighs more. It is a **market-reception
proxy**: nobody rates the Vocazione itself; we read the stars of the businesses that
already perform that function locally. Exactly one value, or **none** when there are
too few rated competitors to mean anything ("dati insufficienti").
_Avoid_: rating (that is one competitor's stars), gradimento del Bene (no Bene is
rated), Consensus (the Round's internal agreement — a different axis entirely).

**Competitor** *(referenced; owned by the monolith's Vocazione↔Concorrenza bridge)*:
A POI in **direct market competition** with a Vocazione — e.g. a spa or gym for
*Dimora del Benessere* — resolved from the Vocazione slug through the fixed
`vocazione_competitors` prefix map and the comune-scoped POI join the **Concorrenza**
map layer already uses. The Scala Likert reads the **same** competitor set the map
paints, then averages those competitors' online stars. Civic Vocazioni (Osservatorio,
Protezione Civile, Hub dei Diritti) have **no real market competitor**, so their
Gradimento is unreliable or empty by construction.
_Avoid_: concorrente generico, "the Vocazione's own POIs" (a Vocazione is stored on no
POI).

### Inherited / referenced

**Active Vocazione** *(owned by the Vocazione Selector)*:
The page-global **filter lens** — one of the 16 Vocazioni, or **none** ("Tutte le
vocazioni") — published on the generalized selection bus (`praim:selection:vocazione`).
The Scala Likert is a **consumer**: no Active Vocazione ⇒ empty state. It is **not** a
Vote and **not** the Round's winning category.

**comune** *(the clicked Territory; owned by the monolith's geography)*:
The administrative unit a Gradimento is computed for — a monolith **region**
(`area_type_id = 3`) resolved from the map click. Delivered to the widget as the
host-set `lat`/`lng` of the click (the same point every Widget receives), which the
widget resolves to its region itself. The competitor POIs, and therefore the
Gradimento, are scoped to exactly this comune.
_Avoid_: province/region in the demographic sense (Gradimento is comune-grained — it
does not roll up to a parent), country.

**Online star-rating**:
The public 1–5 star score a place carries on an online reviews platform, with a count
of how many people gave it. The Scala Likert consumes the **competitors'** stars as the
raw material of the Gradimento; the specific platform and how those stars are kept
current are an implementation concern (this context's ADR), not part of the domain
language.

**POI / Bene**:
A POI is the monolith's point of interest; a **Bene** is the confiscated/public
building (a special POI). The Scala Likert is about **Competitor** POIs in a comune,
**not** about a Bene — so, unlike the Round Manager or Building Characteristic, it does
**not** consume the **Active Workshop** and is not a sensitive widget.

## Flagged ambiguities

- **"Likert" is a gauge, not a Likert scale.** Kept as the product name, but a future
  reader should know it renders a continuous red→green rating gauge with a needle +
  emoji — not the discrete psychometric instrument. Never wire agree/disagree response
  levels in on its account.
- **Gradimento measures the competitors, not the Vocazione.** No one rates "Atelier di
  Ricordi"; the needle reflects the online stars of the photographers, framers and
  galleries that already do that locally. It is a **market-reception proxy**, and it
  inherits the Concorrenza bridge's caveat: **civic** Vocazioni have no genuine
  competitor, so their Gradimento is empty/untrustworthy.
- **Sparse coverage in small borghi.** Many comuni have few rated competitors; below a
  minimum the widget shows **"dati insufficienti"** rather than a misleading needle. The
  exact floor is a tuning decision recorded with the build.
- **Gradimento vs Consensus vs Active Vocazione.** Three Vocazione-touching notions kept
  apart: **Active Vocazione** is the page filter lens; **Consensus** (round-service) is
  participants' internal voting agreement; **Gradimento** (here) is external market
  reception. Same 16-catalog, three different axes.

## Example dialogue

> **Dev:** A user picked "Dimora del Benessere" and clicked Sant'Angelo dei Lombardi.
> What does the needle show?
> **Domain:** The Gradimento — the volume-weighted average of the online stars of that
> comune's wellness competitors (spas, gyms, beauty, nutritionists). If they average
> 4.3★ the needle sits in the green with a 🙂/😍 emoji.
> **Dev:** And if the comune has only one such place, with two reviews?
> **Domain:** Below the minimum, so we show "dati insufficienti," not a confident green.
> A two-review borgo can't tell you how that function is received.
> **Dev:** Does it change if I also select a Bene (Active Workshop)?
> **Domain:** No. The Scala Likert keys off the Active Vocazione + the clicked comune
> only. The Bene/Active Workshop is a different axis it ignores.
> **Dev:** Is this the building's destinazione d'uso, or a Vote?
> **Domain:** Neither — not a current use, not a ballot. It's how the market already
> receives that *kind* of activity here.
