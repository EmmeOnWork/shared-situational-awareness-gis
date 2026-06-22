"""Consensus calculator (pure core).

Nominal exact-match agreement over the 16 Vocazioni, measured as one minus the
normalized Shannon entropy of the vote distribution (service ADR-0002):

    C = 1 - H / ln(min(n, k)),   H = -Σ pᵢ ln pᵢ

normalised by the **realisable** maximum ``ln(min(n, k))`` so that 0 and 1 are
both reachable at any N. No IO, no DB, no HTTP.
"""

from dataclasses import dataclass
from math import log


@dataclass(frozen=True)
class Consensus:
    """Per-Role Consensus (radar branch intensities) and the pooled overall."""

    per_role: dict[str, float]
    overall: float


def _consensus(counts: dict[str, int], k: int) -> float:
    """C = 1 − H/ln(min(n,k)) over the vote counts of one level."""
    n = sum(counts.values())
    if n <= 1:
        return 1.0
    entropy = -sum((c / n) * log(c / n) for c in counts.values() if c > 0)
    return 1.0 - entropy / log(min(n, k))


def _pool(votes_by_role):
    """Collapse Role × Vocazione counts into a single Vocazione → count map."""
    pooled: dict[str, int] = {}
    for counts in votes_by_role.values():
        for vocazione, c in counts.items():
            pooled[vocazione] = pooled.get(vocazione, 0) + c
    return pooled


def compute_consensus(
    votes_by_role: dict[str, dict[str, int]], k: int = 16
) -> Consensus:
    """Per-Role and pooled-overall Consensus, each in [0,1], for one Round's votes.

    ``votes_by_role`` maps a stakeholder Role to its Vocazione → count tally. The
    overall is computed on the pooled votes (service ADR-0002), not the mean of the
    per-Role values.
    """
    per_role = {role: _consensus(counts, k) for role, counts in votes_by_role.items()}
    overall = _consensus(_pool(votes_by_role), k)
    return Consensus(per_role=per_role, overall=overall)
