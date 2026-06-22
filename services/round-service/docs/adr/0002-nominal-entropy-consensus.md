# Consensus is nominal exact-match, measured by normalized Shannon entropy, with raw distributions persisted

Status: accepted

A Round's **Consensus** is the agreement of participants on their **Votes** (each a
Vocazione). We treat the 16 Vocazioni as a **nominal** catalog — no order, no
distance between archetypes — so two participants agree **only on an exact match**.
This rules out the most-cited *ordinal* consensus measure (Tastle–Wierman), which
needs a metric over an ordered scale; imposing a 16×16 distance on the archetypes
would be arbitrary and unvalidatable.

We measure Consensus as **one minus normalized Shannon entropy** of the vote
distribution: `C = 1 − H / ln(min(n, k))`, `H = −Σ pᵢ ln pᵢ`, where `n` is the
number of voters at that level and `k` the catalog size (16). Normalizing by the
**realizable** maximum `ln(min(n,k))` (not a fixed `ln k`) makes `C = 0` at the
maximal dispersion a group of that size can reach and `C = 1` iff unanimity, at any
N — so a within-group disagreement reads as a low percentage instead of being
flattened by the 16-category denominator. A single-person role is defined as
`C = 1`. Consensus is computed at two levels: **per Role** (the radar branch
intensity) and **pooled over all participants** ("consenso totale"); the total is
the measure on the pooled votes, **not** an average of the per-role values.

Crucially we **persist the raw per-(Role × Vocazione) vote counts, N, and timings
for every Round**, not only the final percentage. This makes the whole instrument
**re-derivable offline**: any alternative measure (Simpson/Herfindahl, a different
normalization) can be recomputed from the stored distributions, so the dashboard can
be validated mathematically after the fact and the measure choice is not a one-way
door.

## Considered options

- **Tastle–Wierman ordinal consensus.** Rejected: requires an ordered scale with
  distances; the Vocazioni are nominal.
- **Fixed `ln k` (k=16) normalization.** Rejected: with small groups every
  distribution looks concentrated relative to 16 categories, so the radar would sit
  near-full and within-role disagreement would barely register — contrary to the
  intended spread.
- **Store only the final consensus %.** Rejected: it freezes the measure choice and
  makes later validation or re-derivation impossible; storing raw distributions
  keeps the door open.

## Consequences

- Per-round storage holds an anonymized aggregate (counts by Role × Vocazione),
  enough for the radar and for re-derivation, without persisting a per-user→vote map
  in the analyzable record.
- Because the normalization denominator depends on N (which can change between
  Rounds), raw N must be stored alongside each Round for honest trend analysis.
