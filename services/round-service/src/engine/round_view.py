"""RoundView — the pure projection a room broadcasts to its clients.

One JSON view is fanned out to every connection in a Bene's room on each change.
It is a pure function of the (in-memory) ``ProcessState`` plus, in the recap, the
``RoundOutcome``. Vote *content* (the chosen Vocazioni) never appears before the
recap — the live view carries only counts and the set of user_ids who have voted
(so a client can render its own "HAI VOTATO"); the recap exposes only the
anonymized aggregate (the radar + pooled "consenso totale"). No IO.
"""

from src.engine.recap import RoundOutcome
from src.engine.round_engine import (
    ProcessState,
    ready_count,
    remaining_count,
    voted_count,
)


def _recap_payload(outcome: RoundOutcome) -> dict:
    """The recap's anonymized aggregate: one radar branch per Role present (its
    intra-Role Consensus) and the pooled overall rendered as 'consenso totale'."""
    return {
        "radar": [
            {"role": role, "consensus": consensus}
            for role, consensus in outcome.per_role_consensus.items()
        ],
        "overall": outcome.overall_consensus,
        "n": outcome.n,
    }


def _consensus_payload(state: ProcessState) -> dict:
    """The phase-4 payload the widget renders as 'IL CONSENSO È STATO RAGGIUNTO':
    the winning Vocazione the group converged on (the single value every roster
    member voted) and how many Rounds it took. Pure projection of the terminal
    state's Votes + ordinal; no new-round affordance is offered."""
    return {
        "winner": next(iter(set(state.votes.values()))),
        "rounds": state.round_number,
    }


def project_view(state: ProcessState, outcome: RoundOutcome | None = None) -> dict:
    """Project the room's state into the client-facing view dict.

    ``outcome`` is supplied only in the recap phase (the room builds it off the
    ``RoundClosed`` effect); the live lobby/voting views never carry vote content.
    """
    view = {
        "poi_id": state.poi_id,
        "phase": state.phase,
        "round_number": state.round_number,
        "ready_count": ready_count(state),
        "n": len(state.roster),
        "voted_count": voted_count(state),
        "remaining_count": remaining_count(state),
        "voted_user_ids": list(state.votes.keys()),
        "participants": [
            {"user_id": p.user_id, "role": p.role, "ready": p.ready}
            for p in state.participants
        ],
        "recap": _recap_payload(outcome) if outcome is not None else None,
        "consensus": (
            _consensus_payload(state) if state.phase == "consensus" else None
        ),
    }
    return view
