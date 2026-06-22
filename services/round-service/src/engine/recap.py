"""Recap outcome builder (phase 3 — task 05).

A pure, IO-free join of a **closed** Round's ``ProcessState`` with the task-02
Consensus calculator. ``build_outcome(state)`` turns the Round's secret Votes and
each voter's self-declared stakeholder **Role** into the recap the widget renders
and the ``round_outcomes`` row the persistence edge writes: raw per-(Role ×
Vocazione) counts, N, the radar branches (the Roles **present in this Round**)
each carrying its intra-Role Consensus, and the pooled "consenso totale".

No IO, no DB, no HTTP: timings/duration and the DB write live at the edge that
calls this off the engine's ``RoundClosed`` effect.
"""

from dataclasses import dataclass

from src.consensus.consensus import compute_consensus
from src.engine.round_engine import ProcessState


@dataclass(frozen=True)
class RoundOutcome:
    """A closed Round's analyzable result. ``votes_by_role`` is the raw per-(Role ×
    Vocazione) tally; ``per_role_consensus`` are the radar branch intensities and
    ``overall_consensus`` the pooled "consenso totale" rendered below the radar."""

    poi_id: str
    round_number: int
    n: int
    votes_by_role: dict[str, dict[str, int]]
    per_role_consensus: dict[str, float]
    overall_consensus: float


def _tally_by_role(state: ProcessState) -> dict[str, dict[str, int]]:
    """Join the closed Round's Votes with each voter's Role → per-(Role × Vocazione)
    counts. Only Roles present among the voters appear (the radar's branches)."""
    role_of = {p.user_id: p.role for p in state.participants}
    tally: dict[str, dict[str, int]] = {}
    for user_id, vocazione in state.votes.items():
        role = role_of[user_id]
        bucket = tally.setdefault(role, {})
        bucket[vocazione] = bucket.get(vocazione, 0) + 1
    return tally


def build_outcome(state: ProcessState, k: int = 16) -> RoundOutcome:
    """The recap of a closed Round: raw counts + N + per-Role and pooled Consensus."""
    votes_by_role = _tally_by_role(state)
    consensus = compute_consensus(votes_by_role, k=k)
    return RoundOutcome(
        poi_id=state.poi_id,
        round_number=state.round_number,
        n=len(state.roster),
        votes_by_role=votes_by_role,
        per_role_consensus=consensus.per_role,
        overall_consensus=consensus.overall,
    )
