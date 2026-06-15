# Vocazione Selector Widget (PRAIM)

A standalone, **read-only / stores-nothing** Widget service whose only job is to let
the user pick a **Vocazione** (a target reuse function for the borgo's buildings)
and broadcast that choice page-globally, so a future map layer and other widgets can
re-scope to it. It shares the Janus Supabase database in name only — it owns no
tables — and never edits the monolith.

## Language

### Vocazione domain

**Vocazione**:
One of the **16 fixed archetypes** in *Elenco_Funzioni.pdf* (e.g. *Dimora del
Benessere*, *Atelier di Ricordi*) describing what a building **could be repurposed
into** — its *new/target* destinazione d'uso. A closed catalog, not free text; it is
**not** stored against any building. Identified by a stable slug (`id`) plus an
Italian `label`.
_Avoid_: function (triply overloaded — see Flagged ambiguities), destinazione d'uso
(unqualified — that reads as the *current* use), categoria, tipologia.

**Active Vocazione**:
The single Vocazione currently selected as the page-global **filter lens**, or
**none** ("Tutte le vocazioni" → show everything; carried as `null`). What consumers
react to. Exactly one (or none) at a time. Published on the **generalized selection
bus** (ADR-0005) as an independent axis alongside the **Active Workshop** — *which
kind of reuse*, not *which Bene*; the two never drive each other.
_Avoid_: selected function, active filter (be specific).

**Vocazione Selector**:
The widget itself — a dropdown of the 16 Vocazioni plus a clear entry. Picking one
publishes it as the **Active Vocazione**; it writes nothing and calls no data route
of its own. The catalog of 16 lives inside the bundle (frontend constant).
_Avoid_: Vocazione widget (use Selector), reuse selector (that is the Bene one).

### Inherited / referenced

**Bene**:
The confiscated/public building (a special POI) that a Vocazione could apply to,
owned by the **Building Characteristic** context. The Vocazione is the building's
*possible new* use, but this widget does **not** attach it to any Bene — the link is
deliberately absent (see Flagged ambiguities: "no stored building→Vocazione").

**destinazione d'uso (attuale)**:
The Building Characteristic **Scheda**'s existing free-text field for a Bene's
*current/legal* use, relabelled "(attuale)" to contrast it with the Vocazione (the
*nuova* destinazione). Lives in the characteristic context; named here only to keep
the two senses apart.

**Active Workshop**:
The *other* page-global selection (which Bene is under consideration, ADR-0003),
established by the **Workshop Selector** (reuse-service). Independent of the Active
Vocazione — a dashboard can have both at once, and neither drives the other.

**Widget** (selector/filter variant):
A full-stack Widget that is purely client-side: it ships a custom element behind the
edge gateway and registers in the dashboard catalog, but — unlike demographic
(reads) or characteristic (writes) — it owns **no** data route. Its "output" is a
browser event, not an HTTP response.

## Flagged ambiguities

- **"Function" is triply overloaded.** (1) The monolith's Foursquare-derived POI
  function (`historical | cultural | food-and-drink | other`, colours the map,
  `poi_functions_categories.py`); (2) the generic word; (3) these 16 reuse
  archetypes. Resolved: the 16 are **Vocazioni**; never call them "functions" in our
  code or UI.
- **"destinazione d'uso" — current vs new.** The Scheda's free-text field is the
  **current** use → labelled "(attuale)". The **Vocazione** is the *possible new*
  destinazione. Always say which.
- **"riuso / reuse" is overloaded.** `reuse-service` is the **Bene** selector; a
  Bene is a "reuse-POI"; "reuse data" is the Scheda. A **Vocazione** is a *different
  axis* (a kind of reuse), not a Bene. Prefer **Vocazione** over any "reuse…" phrase.
- **No stored building→Vocazione link (deliberate).** This widget records nothing; a
  Bene is never tagged with a Vocazione. A map layer that shows "only buildings of
  the selected Vocazione" therefore has **no data to query yet** and is explicitly
  out of scope — the widget only guarantees a clean, consumable broadcast.

## Example dialogue

> **Dev:** A user picks "Dimora del Benessere." What gets written?
> **Domain:** Nothing. The Selector publishes it as the **Active Vocazione** on the
> page bus and reflects the slug into the URL. No table, no Bene is touched.
> **Dev:** So how does the map then show only "Dimora del Benessere" buildings?
> **Domain:** Today it can't — there is no stored building→Vocazione link. That map
> layer is future work; all this widget promises is the broadcast a future layer (or
> any other widget) can consume.
> **Dev:** Is this the same as a building's "destinazione d'uso"?
> **Domain:** No. That Scheda field is the building's **current** use — "(attuale)".
> A Vocazione is a *possible new* use, chosen from the fixed 16, and never saved.
> **Dev:** And the Active Workshop?
> **Domain:** A separate axis — *which Bene*, not *which Vocazione*. You can have
> both selected; they don't affect each other.
