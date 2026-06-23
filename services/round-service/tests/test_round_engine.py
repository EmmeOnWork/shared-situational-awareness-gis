"""Unit tests for the pure Round engine — lobby (phase 0) transitions.

Pure state-machine style (no DB, no WebSocket): feed lobby events through the
public ``apply(state, event)`` reducer and assert the next state and emitted
side-effects. Covers the self-forming roster, the service-owned Role catalog, the
live ready count, and the ready-gate that opens Round 1 freezing N at the ready
set (PRD module 2; service ADR-0001; task 03).

The stakeholder Role is no longer self-declared in the lobby: it rides ``Join``
(the user's account Role, from the JWT claim). ``j(user)`` is a tiny helper that
joins with a default Role where the specific value is irrelevant to the test.
"""

import pytest

from src.engine.round_engine import (
    Join,
    Ready,
    OpenRound,
    CastVote,
    RoundOpened,
    RoundClosed,
    ConsensusReached,
    initial_state,
    apply,
    ready_count,
    voted_count,
    remaining_count,
)


def j(user_id, role="tecnico"):
    """Join carrying the account's stakeholder Role (defaulted where irrelevant)."""
    return Join(user_id, role)


def _drive(state, events):
    """Fold a sequence of events through the reducer, collecting all effects."""
    effects = []
    for event in events:
        state, emitted = apply(state, event)
        effects.extend(emitted)
    return state, effects


# --- Inner unit cycles -------------------------------------------------------


def test_join_adds_a_participant_with_its_account_role():
    """The roster is self-forming: opening the widget on a Bene (Join) creates a
    participant whose stakeholder Role is the one its account carries (from the JWT
    claim), not ready yet, no effect, and the lobby phase is unchanged."""
    state, effects = apply(initial_state("bene-1"), Join("u1", "tecnico"))

    assert [p.user_id for p in state.participants] == ["u1"]
    assert state.participants[0].role == "tecnico"
    assert state.participants[0].ready is False
    assert state.phase == "lobby"
    assert effects == []


def test_join_is_idempotent():
    """Re-opening the widget (a second Join for the same user) does not duplicate
    the participant — the roster tracks user×Bene, not connections."""
    state, _ = apply(initial_state("bene-1"), j("u1"))
    state, effects = apply(state, j("u1"))

    assert [p.user_id for p in state.participants] == ["u1"]
    assert effects == []


def test_join_role_outside_catalog_is_rejected():
    """A Role not in the service-owned catalog (or missing, e.g. a legacy token with
    no claim) is refused (ValueError) at join; the bad value never reaches a roster
    entry or a radar branch."""
    with pytest.raises(ValueError):
        apply(initial_state("bene-1"), Join("u1", "banana"))

    with pytest.raises(ValueError):
        apply(initial_state("bene-1"), Join("u1", None))


def test_ready_marks_participant_and_updates_live_count():
    """Ready flips a Participant's ready flag; ``ready_count`` is the live tally the
    lobby shows ('quanti pronti'), so clients can render it as it changes."""
    state, _ = _drive(
        initial_state("bene-1"),
        [j("u1"), j("u2"), Ready("u1")],
    )

    assert ready_count(state) == 1
    state, effects = apply(state, Ready("u2"))
    assert ready_count(state) == 2
    assert effects == []


def test_open_round_freezes_roster_at_the_ready_set():
    """OpenRound takes the lobby to Round 1: the roster freezes at exactly the
    ready Participants (N), the phase becomes voting, and a RoundOpened side-effect
    carries the Bene and N. A present-but-not-ready Participant is excluded from N."""
    state, _ = _drive(
        initial_state("bene-1"),
        [j("u1"), Ready("u1"), j("u2"), Ready("u2"), j("u3")],
    )

    state, effects = apply(state, OpenRound())

    assert state.round_number == 1
    assert state.phase == "voting"
    assert set(state.roster) == {"u1", "u2"}
    assert "u3" not in state.roster
    assert effects == [RoundOpened(poi_id="bene-1", round_number=1, n=2)]


def test_open_round_needs_at_least_two_ready():
    """A consensus process is multi-party: the ready-gate refuses a Round with fewer
    than two ready Participants — neither nobody ready, nor a single person who
    readied alone (you cannot start a Round by yourself)."""
    state, _ = apply(initial_state("bene-1"), j("u1"))
    with pytest.raises(ValueError):
        apply(state, OpenRound())  # nobody ready

    state, _ = apply(state, Ready("u1"))
    with pytest.raises(ValueError):
        apply(state, OpenRound())  # exactly one ready is still refused


def test_latecomer_after_open_is_queued_not_in_denominator():
    """A user who opens the widget after the Round has opened becomes a Participant
    (joins the *next* Round) but is not added to the current frozen roster N, so
    'N/N hanno votato' stays well-defined."""
    state, _ = _drive(
        initial_state("bene-1"),
        [j("u1"), Ready("u1"), j("u2"), Ready("u2"), OpenRound()],
    )

    state, effects = apply(state, j("u3"))

    assert "u3" in [p.user_id for p in state.participants]
    assert "u3" not in state.roster
    assert set(state.roster) == {"u1", "u2"}
    assert state.round_number == 1
    assert effects == []


# --- Voting & close (phases 1→2) --------------------------------------------


def _opened(*ready_users):
    """A Bene with the given users joined, ready and Round 1 open (roster = N)."""
    events = []
    for u in ready_users:
        events += [j(u), Ready(u)]
    events.append(OpenRound())
    state, _ = _drive(initial_state("bene-1"), events)
    return state


def test_cast_vote_records_a_roster_members_vote():
    """A roster member casts one final Vote for a Vocazione; it is recorded against
    the open Round, the phase stays voting (not yet N/N) and no effect fires (a Vote
    is local feedback, never a Notification)."""
    state = _opened("u1", "u2")

    state, effects = apply(state, CastVote("u1", "casa-popolare"))

    assert state.votes == {"u1": "casa-popolare"}
    assert state.phase == "voting"
    assert effects == []


def test_a_vote_is_immutable_within_the_round():
    """A Vote is final on confirmation: a second CastVote by the same Participant
    within the Round is refused (ValueError) and the original Vote is unchanged, so
    'X rimasti' only ever counts down."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))

    with pytest.raises(ValueError):
        apply(state, CastVote("u1", "spazio-culturale"))


def test_a_non_roster_participant_cannot_vote_in_this_round():
    """The denominator is the frozen roster: a Participant who joined mid-Round (or
    never readied) is not in N, so their CastVote is refused (ValueError) and the
    'N/N hanno votato' close stays well-defined."""
    state = _opened("u1", "u2")
    state, _ = apply(state, j("u3"))  # latecomer, queued for the next Round

    with pytest.raises(ValueError):
        apply(state, CastVote("u3", "casa-popolare"))


def test_round_closes_only_at_full_presence_unanimity():
    """A Round closes for everyone the instant the last (N/N) Vote lands — no
    timeout/quorum: with N=2, the first Vote leaves the Round open with no effect;
    the second closes it (RoundClosed) and moves the phase to recap."""
    state = _opened("u1", "u2")

    state, effects = apply(state, CastVote("u1", "casa-popolare"))
    assert state.phase == "voting"
    assert effects == []

    state, effects = apply(state, CastVote("u2", "spazio-culturale"))
    assert state.phase == "recap"
    assert effects == [RoundClosed(poi_id="bene-1", round_number=1, n=2)]


# --- New round: re-open through the same ready-gate (phase 3) ----------------


def test_round_close_resets_ready_flags():
    """Closing a Round clears every Participant's ready flag: the next Round opens
    through the phase-3 "pronti a ricominciare" ready-gate, so the live ready count
    behind "inizia un nuovo round" starts fresh at 0 rather than re-firing the old
    ready set."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    state, _ = apply(state, CastVote("u2", "spazio-culturale"))  # split N/N close → recap

    assert state.phase == "recap"
    assert ready_count(state) == 0
    assert all(not p.ready for p in state.participants)


def test_new_round_reopens_via_the_same_ready_gate():
    """From the recap, the ready set re-opens a Round through the SAME ready-gate as
    Round 1: re-readied Participants form the new frozen roster, the ordinal advances,
    the previous Round's Votes are cleared, and a RoundOpened carries the new N."""
    state = _opened("u1", "u2")
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    state, _ = apply(state, CastVote("u2", "spazio-culturale"))  # Round 1 closes

    # Both signal ready for the next Round → the roster re-freezes at the new set.
    state, _ = apply(state, Ready("u1"))
    state, _ = apply(state, Ready("u2"))
    state, effects = apply(state, OpenRound())

    assert state.round_number == 2
    assert state.phase == "voting"
    assert set(state.roster) == {"u1", "u2"}
    assert state.votes == {}
    assert effects == [RoundOpened(poi_id="bene-1", round_number=2, n=2)]


def test_latecomer_joins_the_next_round():
    """A user who joined mid-Round-1 (excluded from that frozen N) can ready up
    between Rounds and is counted in the next Round's denominator — the roster can
    change only between Rounds."""
    state = _opened("u1", "u2")
    state, _ = apply(state, j("u3"))  # latecomer, not in Round 1's N
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    state, _ = apply(state, CastVote("u2", "spazio-culturale"))  # split close → recap

    # Everyone (including the latecomer) readies for Round 2.
    for u in ("u1", "u2", "u3"):
        state, _ = apply(state, Ready(u))
    state, effects = apply(state, OpenRound())

    assert set(state.roster) == {"u1", "u2", "u3"}
    assert effects == [RoundOpened(poi_id="bene-1", round_number=2, n=3)]


# --- Acceptance test (outer tracer): a full lobby opening Round 1 ------------


def test_lobby_opens_round_one_freezing_ready_roster():
    """Three users join (each bringing its account Role); two ready up and start
    Round 1. The roster freezes at the ready set (N=2), a RoundOpened side-effect
    fires, and a fourth latecomer who joins after the open is NOT in the current
    denominator."""
    state = initial_state("bene-1")

    state, effects = _drive(
        state,
        [
            Join("u1", "istituzionale"), Ready("u1"),
            Join("u2", "economico"), Ready("u2"),
            Join("u3", "tecnico"),  # present, never readies
            OpenRound(),
        ],
    )

    assert state.round_number == 1
    assert state.phase == "voting"
    assert set(state.roster) == {"u1", "u2"}  # N frozen at the ready set
    assert effects == [RoundOpened(poi_id="bene-1", round_number=1, n=2)]

    # Latecomer joins after the Round opened → queued for the next Round.
    state, effects = apply(state, Join("u4", "tecnico"))
    assert "u4" not in state.roster
    assert state.round_number == 1
    assert effects == []


# --- Acceptance test (outer tracer): voting through a full N/N close ---------


def test_round_closes_for_everyone_the_instant_the_last_vote_lands():
    """Phases 1→2: an open Round with N=3 collects one final Vote per roster
    member. The live tally counts down as each Vote lands; a mid-Round joiner is
    excluded from N; and the Round closes for everyone exactly when the third
    (N/N) Vote lands — emitting RoundClosed and moving to the recap phase."""
    state, _ = _drive(
        initial_state("bene-1"),
        [
            j("u1"), Ready("u1"),
            j("u2"), Ready("u2"),
            j("u3"), Ready("u3"),
            OpenRound(),
        ],
    )
    assert state.roster == ("u1", "u2", "u3")
    assert (voted_count(state), remaining_count(state)) == (0, 3)

    # A latecomer joins mid-Round → in the next Round, not this denominator.
    state, _ = apply(state, j("u4"))

    # Votes land one by one; the tally updates live and the Round stays open.
    state, effects = apply(state, CastVote("u1", "casa-popolare"))
    assert (voted_count(state), remaining_count(state)) == (1, 2)
    assert state.phase == "voting"
    assert effects == []

    state, effects = apply(state, CastVote("u2", "spazio-culturale"))
    assert (voted_count(state), remaining_count(state)) == (2, 1)
    assert effects == []

    # The third (N/N) Vote closes the Round for everyone, the instant it lands.
    state, effects = apply(state, CastVote("u3", "casa-popolare"))
    assert (voted_count(state), remaining_count(state)) == (3, 0)
    assert state.phase == "recap"
    assert effects == [RoundClosed(poi_id="bene-1", round_number=1, n=3)]


# --- Acceptance test (outer tracer): consensus reached is terminal (phase 4) -


def test_unanimous_close_reaches_terminal_consensus_and_cannot_reopen():
    """Phase 4 end-to-end over the pure core: a split Round 1 closes into the recap
    (still re-openable), then Round 2 closes with everyone on the SAME Vocazione —
    overall Consensus = 100%. That terminal close moves to the ``consensus`` phase
    (not ``recap``) and emits a single ``ConsensusReached`` carrying the winning
    Vocazione and how many Rounds it took; from there a settled decision can't be
    reopened — ``OpenRound`` is refused."""
    state = _opened("u1", "u2")

    # Round 1 is split → ordinary recap, still re-openable.
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    state, effects = apply(state, CastVote("u2", "spazio-culturale"))
    assert state.phase == "recap"
    assert effects == [RoundClosed(poi_id="bene-1", round_number=1, n=2)]

    # Round 2: the group converges on one Vocazione → unanimity.
    state, _ = apply(state, Ready("u1"))
    state, _ = apply(state, Ready("u2"))
    state, _ = apply(state, OpenRound())
    state, _ = apply(state, CastVote("u1", "casa-popolare"))
    state, effects = apply(state, CastVote("u2", "casa-popolare"))

    # Terminal: phase 4, a single ConsensusReached (winner + round count), no RoundClosed.
    assert state.phase == "consensus"
    assert effects == [
        ConsensusReached(
            poi_id="bene-1", round_number=2, winner="casa-popolare", rounds=2
        )
    ]

    # A settled decision cannot be reopened: the ready-gate is closed for good.
    state, _ = apply(state, Ready("u1"))
    with pytest.raises(ValueError):
        apply(state, OpenRound())
