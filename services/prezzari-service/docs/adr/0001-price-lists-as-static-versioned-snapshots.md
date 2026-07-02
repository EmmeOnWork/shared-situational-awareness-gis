# Both price lists are static versioned snapshots in owned tables, latest-only, with no runtime calls to the source sites

Status: accepted

**I Prezziari** shows two reference price lists side by side: the **Prezziario di
Locazione** (Agenzia delle Entrate **OMI** rental quotations, comune-scoped) and the
**Prezzario dei Lavori** (a curated renovation slice of the **Regione Campania**
public-works price list, region-fixed). Both are **published, slow-moving reference
data** — the OMI is released **semestrally**, the Campania prezzario **annually** (the
current edition is 2026). Neither drifts continuously the way a live market signal does.

We therefore hold **both lists as static, versioned snapshots in the Widget's own
tables**, ingested **offline** from the source publications, and the Widget reads only
from those tables — it makes **zero calls to `agenziaentrate.gov.it` or
`prezzario.regione.campania.it` at runtime**. Each snapshot is stored with its
**publication label** (OMI semester / prezzario year), but the Widget **shows only the
latest** of each: there is no historical comparison. When a new edition is published, the
snapshot is **re-ingested manually** (an offline import, like the geo-layers ogr2ogr
ingest). Only the **Campania** comuni are ingested for the OMI, to match the region-bound
Lista B and the Campania-bound map.

This makes `prezzari-service` the second read-side Widget to **own tables** (after the
Scala Likert), but — unlike the Likert — the data is **static and re-derivable**, so
there is **no background refresh worker, no TTL, no external paid provider and no live
fan-out**. The Widget computes nothing: it presents the raw published figures and the
user weighs them.

## Considered options

- **Live fetch / scrape per click.** Rejected: the two source sites are outside our
  control (an HTML consultation form and a SPA), so their markup/endpoints can change
  without notice; a runtime dependency on their uptime and shape is fragile and slow, and
  buys nothing because the data only changes once or twice a year.
- **Cache with a TTL + background refresh worker (the Scala Likert pattern).** Rejected as
  overkill here: the Likert chases a **continuously drifting** external signal (Google
  ratings) from a **paid** provider under a caching ceiling, so it needs a worker, a TTL
  and a call budget. These lists are **published editions** that change semestrally /
  annually — there is no drift to chase and no per-call cost, so a refresh worker would be
  machinery guarding against a change that happens on a human, calendar cadence. A manual
  re-ingest on publication is simpler and sufficient.
- **Static seed committed in the repo / shipped in the JS bundle.** Acceptable for the
  curated prezzario slice (a few hundred voci), but **not** for the OMI: every Campania
  comune × Zona OMI × typology row is far too much to bake into the widget bundle. Kept in
  **tables** for both, so the reading path is uniform and the bundle stays small.
- **Keep the full OMI (all of Italy) and/or the full prezzario (all chapters).** Rejected:
  the map and the Lista B are Campania-bound and the widget is about **building reuse**, so
  a national OMI and the roads/aqueducts chapters are dead weight. The scope is cut to
  Campania comuni + the renovation Capitoli.
- **Keep the publication history for time comparison.** Rejected for now: the product need
  is "what does it cost / rent **today**", so only the latest edition is shown. History
  could be added later without changing the snapshot model (the publication label is
  already stored).

## Consequences

- **`prezzari-service` owns tables but with no live machinery.** No worker, no TTL, no
  provider key, no runtime egress — the snapshot tables are the whole data plane. The data
  is derived/disposable (re-ingestible from the published sources), so it is not
  source-of-truth and can be rebuilt.
- **Staleness is bounded by the manual re-ingest cadence, and is visible.** Between
  publications the figures are fixed by construction; the Widget surfaces the
  **publication label** so the user knows which edition they are reading. A missed
  re-ingest simply keeps showing the previous (still-valid-enough) edition.
- **The curated renovation slice is an editorial choice that must be re-curated.** Picking
  which Capitoli count as "ristrutturazione / recupero" is a human decision baked into the
  ingest; a new prezzario edition needs the slice re-confirmed, not just re-imported.
- **The two lists degrade independently.** A comune with no published OMI shows an empty
  left list while the regional Lista B stays visible; neither list depends on the other.
- **Campania-only OMI is a deliberate scope cut.** A click outside Campania resolves to no
  comune (neutral state). Widening to other regions later means both a larger OMI ingest
  and a different (per-region) works prezzario — a bigger change, accepted as out of scope.
