"""The Gradimento measure (pure core) — PRD "The Gradimento"; service ADR-0001.

The Gradimento is the **pooled online star-rating** of a Vocazione's market
Competitors in the clicked comune:

    Gradimento = Σ(ratingᵢ × nᵢ) / Σ nᵢ

over the competitors that have a confident Google match **and** a cached rating,
where ``ratingᵢ`` is a place's 1–5 average and ``nᵢ`` its review count. Each review
counts once, so a busier competitor weighs more.

States (server-decided here): **zero** rated competitors ⇒ ``insufficient`` (no
needle, "dati insufficienti"); pooled reviews below ``FLOOR`` ⇒ ``ok`` but
``low_confidence`` (needle shown, faded, "pochi dati"); otherwise plain ``ok``. The
``no_competitors`` state (a civic Vocazione with an empty prefix map) is the
router's call — this calculator only ever sees the *rated* set. No IO, no DB, no
HTTP.
"""

from dataclasses import dataclass
from typing import List, Optional

#: Minimum pooled review count for a confident Gradimento; below it ⇒ low-confidence.
#: Tunable (PRD default 15); mirrors the frontend ``scale.ts`` FLOOR.
FLOOR = 15


@dataclass(frozen=True)
class RatedPlace:
    """One competitor with a cached rating: its 1–5 average and review count. The
    calculator never sees unrated/unmatched competitors — they are filtered out
    upstream (a wrong or absent match must not distort the pooled mean)."""

    rating: float
    n_ratings: int


@dataclass(frozen=True)
class Gradimento:
    """The computed measure and its state for one (Vocazione, comune)."""

    status: str  # "ok" | "insufficient"
    value: Optional[float]  # 1..5 pooled mean; None unless status == "ok"
    total_reviews: int  # Σ nᵢ — the pooled review count behind the value
    n_rated: int  # competitors that contributed (confident match + rating)
    low_confidence: bool  # True when total_reviews < FLOOR (an estimate)


def compute_gradimento(rated: List[RatedPlace], floor: int = FLOOR) -> Gradimento:
    """Pool ``rated`` competitors into a Gradimento and its state.

    Args:
        rated: the competitors with a confident match AND a cached rating (the
            router filters out the rest). An empty list is the "all-unrated" /
            "none matched" case.
        floor: the low-confidence threshold on the pooled review count.

    Returns:
        ``insufficient`` with a null value when nothing rated (or no reviews at
        all); otherwise ``ok`` with the pooled mean, flagged ``low_confidence``
        when the pooled review count is below ``floor``.
    """
    total_reviews = sum(p.n_ratings for p in rated)

    # No rated competitor — or rated rows that carry no reviews — is no signal:
    # withhold the needle rather than divide by zero or trust an empty average.
    if not rated or total_reviews <= 0:
        return Gradimento(
            status="insufficient",
            value=None,
            total_reviews=total_reviews,
            n_rated=len(rated),
            low_confidence=False,
        )

    value = sum(p.rating * p.n_ratings for p in rated) / total_reviews
    return Gradimento(
        status="ok",
        value=value,
        total_reviews=total_reviews,
        n_rated=len(rated),
        low_confidence=total_reviews < floor,
    )
