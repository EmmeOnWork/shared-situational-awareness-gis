"""RoundView — the pure projection a room broadcasts to its clients.

One JSON view is fanned out to every connection in a Bene's room on each change.
It is a pure function of the (in-memory) ``ProcessState`` plus, in the recap, the
``RoundOutcome``. Vote *content* (the chosen Vocazioni) never appears before the
recap — the live view carries only counts and the set of user_ids who have voted
(so a client can render its own "HAI VOTATO"); the recap exposes only the
anonymized aggregate (the radar + pooled "consenso totale"). No IO.
"""

from collections.abc import Iterable

from src.chat.chat_store import AnonymousMessage
from src.engine.recap import RoundOutcome
from src.engine.round_engine import (
    ProcessState,
    ready_count,
    remaining_count,
    voted_count,
)


def _recap_payload(outcome: RoundOutcome) -> dict:
    """The recap's anonymized aggregate: one radar branch per Role present carrying its
    intra-Role Consensus AND how many voters that Role had (the 'es. 3 tecnici' the
    fullscreen radar shows), plus the pooled overall rendered as 'consenso totale'.
    A count is the sum of the Role's per-Vocazione tally; still anonymous (a headcount,
    never who)."""
    counts = {role: sum(tally.values()) for role, tally in outcome.votes_by_role.items()}
    return {
        "radar": [
            {"role": role, "consensus": consensus, "count": counts.get(role, 0)}
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


def _chat_payload(messages: Iterable[AnonymousMessage]) -> list[dict]:
    """The Chat's anonymised stream as JSON-safe dicts (timestamp → ISO 8601). Never
    carries an author — the messages are already the anonymised read shape; the room
    decides *whether* this recipient gets the stream (post-vote / recap) at all."""
    return [
        {
            "round_number": m.round_number,
            "body": m.body,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in messages
    ]


def project_view(
    state: ProcessState,
    outcome: RoundOutcome | None = None,
    chat: Iterable[AnonymousMessage] = (),
) -> dict:
    """Project the room's state into the client-facing view dict.

    ``outcome`` is supplied only in the recap phase (the room builds it off the
    ``RoundClosed`` effect); the live lobby/voting views never carry vote content.
    ``chat`` is the anonymised stream the room already gated for this recipient
    (empty when they may not yet read it — before they have voted).
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
        "chat": _chat_payload(chat),
    }
    return view
