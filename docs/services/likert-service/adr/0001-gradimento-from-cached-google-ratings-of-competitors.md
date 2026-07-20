# Gradimento is the pooled Google star-rating of a Vocazione's market competitors, cached and background-refreshed

Status: accepted

The **Scala Likert** answers "how well-received is the Active Vocazione on the clicked
comune?" with a single number, the **Gradimento**. Nobody rates a Vocazione directly,
so we use a **market-reception proxy**: the public online star-ratings of the POIs
already in **direct competition** with that Vocazione in that comune — the exact
**Competitor** set the Concorrenza map layer paints (the `vocazione_competitors` prefix
map + the comune-scoped `regions → region_areas → areas → poi_area_lookup → pois`
join). The widget **copies** that mapping into its own service (the strangler "copy"
pattern, like `selection-bus.ts`) and reads the competitor POIs from the shared DB; it
never imports monolith code nor calls a monolith endpoint.

The only star-ratings already in the stack are the monolith's MongoDB
`POIS_F&D_reviews`, which are **food-and-drink only** — too narrow, since a Vocazione's
competitors span spas, offices, galleries and clinics. We therefore source ratings from
**Google Places**, broad enough to cover every competitor category. Our POIs are
foursquare-native (`pois.source_id` is an fsq_id), so there is no shared key with
Google: we **fuzzy-match each competitor POI to a Google Place by name + coordinates**,
store the resolved `google_place_id` **permanently** (allowed by Google's terms), and
cache the place's `rating` + `user_ratings_total` with a **≤30-day TTL** (the terms'
caching ceiling). A **background job refreshes the whole competitor universe — all
comuni in the DB** — so any clicked comune answers instantly from cache; the widget
itself **never calls Google live**. This makes `likert-service` the **first read-side
Widget to own tables** (the place_id map + the ratings cache) and the **first to depend
on an external paid provider**.

The Gradimento is the **pooled** mean over all reviews: `Σ(ratingᵢ × nᵢ) / Σ nᵢ` across
the comune's rated competitors (each public review counts once, so a busier competitor
weighs more). Below a small review floor the needle is shown but flagged low-confidence
("pochi dati"); with **zero** rated competitors it is "dati insufficienti"; civic
Vocazioni, which have no genuine market competitor, are empty by construction.

## Considered options

- **Foursquare Places API, matched by the stored fsq_id.** Tempting — a clean 1:1
  identity with no fuzzy matching, since our POIs are foursquare-native. Rejected for
  **coverage**: Foursquare's rating density in small Italian borghi is thin, and broad
  review coverage is the whole point. We accept fuzzy matching as the price of coverage.
- **The existing F&D review pipeline, widened past food-and-drink.** Rejected: that
  harvester lives upstream, outside this repo, and isn't ours to change here; and it is
  keyed to a narrow collection.
- **Live per click (no rating cache) / lazy on-demand cache.** Rejected: a click would
  fan out to dozens of paid Place Details calls (slow, costly, repeated), and a lazy
  cache makes the first view of every (Vocazione, comune) slow. A background-refreshed
  cache keeps reads instant and cost predictable per TTL cycle.
- **Bounded harvest (pilot borghi only, or pilot + lazy others).** Rejected in favour of
  **all comuni**, so the widget works instantly everywhere; the cost of that breadth is
  accepted (see Consequences).
- **Mean of per-POI averages, or credibility-weighted (Bayesian) shrink.** Rejected:
  pooling is the simplest to justify in the detail modal and reads as "total
  satisfaction volume." Trade-off accepted: one very popular competitor can dominate a
  comune's needle.
- **ABSA aspect-sentiment in the modal** (as the F&D reviews carry). Out of scope: that
  sentiment is a property of the Mongo pipeline, not of Google ratings; the modal
  justifies the number with a per-competitor ★ breakdown instead.

## Consequences

- **Cost scales with the unique competitor universe, refreshed every TTL cycle.** That
  universe is plausibly a few thousand foursquare POIs (the concorrenza counts run
  80–441 *per* Vocazione across all comuni), so ≈ that many Place Details calls per
  ≤30-day cycle plus a one-time place_id matching pass. Verify against current Google
  pricing and **cap the refresher with a monthly call budget**, so a price change or a
  matching bug cannot run away.
- **Fuzzy matching will mis-pair some POIs** in dense areas (same name, nearby). Guard
  with a distance + name-similarity threshold and **exclude** a competitor when no
  confident match exists, rather than attaching a wrong rating. Unmatched competitors
  simply don't contribute to the pool.
- **`likert-service` owns tables**, unlike every prior read widget. The cache is
  derived/disposable (re-derivable from Google), so it is not source-of-truth and can be
  rebuilt — but it is shared-schema state that needs a migration and a refresh worker.
- **The cache is eventually-consistent by ≤30 days.** A competitor that opened, closed
  or whose rating moved since the last refresh is stale within the TTL — acceptable for a
  market-reception proxy, and the modal shows "aggiornato il …" so the staleness is
  visible.
- **Reads the shared DB for the competitor set by copying `vocazione_competitors`.** If
  the monolith re-tunes that mapping, the copy drifts until re-synced — the same accepted
  duplication every Widget makes (ADR-0001 shared DB, strangler copy pattern).
