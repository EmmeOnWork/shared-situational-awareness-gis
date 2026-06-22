"""Unit tests for the pure RoundView projection (the WS broadcast payload).

A room fans out ONE JSON view to every connected client on each change; the view
is a pure projection of the (in-memory) ``ProcessState`` plus, in the recap, the
``RoundOutcome``. These assert the projection — phase, the lobby roster + live
ready count, the live X/N tally, and the recap's radar + consenso totale — without
any WebSocket or DB. Vote *content* never appears before the recap (independence);
the recap carries only the anonymized aggregate.
"""

from src.engine.round_engine import (
    Join,
    DeclareRole,
    Ready,
    OpenRound,
    CastVote,
    initial_state,
    apply,
)
from src.engine.recap import build_outcome
from src.engine.round_view import project_view


def _drive(state, events):
    for event in events:
        state, _ = apply(state, event)
    return state


def test_lobby_view_shows_roster_and_live_ready_count():
    """In the lobby the view carries each Participant (user, declared Role, ready)
    and the live ready count the 'quanti pronti' / start button reads."""
    state = _drive(
        initial_state("bene-1"),
        [Join("u1"), DeclareRole("u1", "tecnico"), Ready("u1"), Join("u2")],
    )

    view = project_view(state)

    assert view["phase"] == "lobby"
    assert view["round_number"] == 0
    assert view["ready_count"] == 1
    assert {"user_id": "u1", "role": "tecnico", "ready": True} in view["participants"]
    assert {"user_id": "u2", "role": None, "ready": False} in view["participants"]


def test_voting_view_shows_live_tally_and_who_has_voted():
    """While voting, the view carries the frozen N, the live voted/remaining tally
    and the set of user_ids who have voted (so a client can show its own 'HAI
    VOTATO') — but never the Vocazioni chosen (vote content stays secret)."""
    state = _drive(
        initial_state("bene-1"),
        [Join("u1"), Ready("u1"), Join("u2"), Ready("u2"), OpenRound(), CastVote("u1", "residenziale")],
    )

    view = project_view(state)

    assert view["phase"] == "voting"
    assert view["n"] == 2
    assert view["voted_count"] == 1
    assert view["remaining_count"] == 1
    assert view["voted_user_ids"] == ["u1"]
    assert "residenziale" not in str(view)  # vote content is not leaked pre-recap


def test_recap_view_carries_radar_and_consenso_totale():
    """In the recap the view carries the radar (a branch per Role present with its
    intra-Role Consensus), the pooled 'consenso totale', and the live ready count
    behind 'inizia un nuovo round' (reset to 0 on close)."""
    state = _drive(
        initial_state("bene-1"),
        [
            Join("u1"), DeclareRole("u1", "istituzionale"), Ready("u1"),
            Join("u2"), DeclareRole("u2", "economico"), Ready("u2"),
            OpenRound(),
            CastVote("u1", "residenziale"), CastVote("u2", "commerciale"),
        ],
    )

    view = project_view(state, outcome=build_outcome(state))

    assert view["phase"] == "recap"
    assert view["ready_count"] == 0
    recap = view["recap"]
    assert {b["role"] for b in recap["radar"]} == {"istituzionale", "economico"}
    assert all(0.0 <= b["consensus"] <= 1.0 for b in recap["radar"])
    assert 0.0 <= recap["overall"] <= 1.0


def test_terminal_view_shows_winner_and_round_count_no_new_round():
    """At 100% (phase 4) the view replaces the recap with the consensus-reached
    payload the widget renders as 'IL CONSENSO È STATO RAGGIUNTO': the winning
    Vocazione and how many Rounds it took. There is no recap and no 'inizia un nuovo
    round' affordance — a settled decision can't be reopened."""
    state = _drive(
        initial_state("bene-1"),
        [
            Join("u1"), DeclareRole("u1", "istituzionale"), Ready("u1"),
            Join("u2"), DeclareRole("u2", "economico"), Ready("u2"),
            OpenRound(),
            CastVote("u1", "residenziale"), CastVote("u2", "residenziale"),
        ],
    )

    view = project_view(state)

    assert view["phase"] == "consensus"
    assert view["consensus"] == {"winner": "residenziale", "rounds": 1}
    assert view["recap"] is None
