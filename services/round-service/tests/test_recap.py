"""Unit tests for the recap outcome builder (phase 3 — task 05).

Pure-core style (no DB, no WebSocket): drive a Bene's process through the engine
to a full N/N close, then ``build_outcome`` over the closed ``ProcessState`` and
assert the recap the widget renders and the ``round_outcomes`` row the persistence
edge will write — raw per-(Role × Vocazione) counts, N, the radar branches (Roles
present in the Round) with their intra-Role Consensus, and the pooled "consenso
totale". The Consensus itself is the task-02 calculator; this slice is the join of
the closed Round's Votes with each voter's stakeholder Role.
"""

import pytest

from src.engine.round_engine import (
    Join,
    DeclareRole,
    Ready,
    OpenRound,
    CastVote,
    RoundOpened,
    initial_state,
    apply,
    ready_count,
)
from src.engine.recap import build_outcome


def _closed(*voters):
    """Drive a Bene to a closed Round 1. ``voters`` are (user_id, role, vocazione)
    triples: each joins, declares its Role, readies, then casts its Vote — the last
    Vote (N/N) closes the Round into the recap phase."""
    state = initial_state("bene-1")
    for user_id, role, _ in voters:
        state, _ = apply(state, Join(user_id))
        state, _ = apply(state, DeclareRole(user_id, role))
        state, _ = apply(state, Ready(user_id))
    state, _ = apply(state, OpenRound())
    for user_id, _, vocazione in voters:
        state, _ = apply(state, CastVote(user_id, vocazione))
    return state


# --- Inner unit cycles -------------------------------------------------------


def test_outcome_tallies_votes_by_role():
    """The closed Round's Votes are joined with each voter's stakeholder Role into
    raw per-(Role × Vocazione) counts — the analyzable record the recap renders and
    ``round_outcomes`` persists."""
    state = _closed(
        ("u1", "istituzionale", "residenziale"),
        ("u2", "economico", "commerciale"),
        ("u3", "economico", "commerciale"),
    )

    outcome = build_outcome(state)

    assert outcome.votes_by_role == {
        "istituzionale": {"residenziale": 1},
        "economico": {"commerciale": 2},
    }


def test_radar_branches_are_roles_present_in_the_round():
    """The radar's branches are exactly the stakeholder Roles held by voters in this
    Round — a catalog Role nobody declared gets no branch (no phantom 0-intensity
    spoke). 'tecnico', 'sociale', 'ambientale' are in the catalog but absent here."""
    state = _closed(
        ("u1", "istituzionale", "residenziale"),
        ("u2", "economico", "commerciale"),
    )

    outcome = build_outcome(state)

    assert set(outcome.per_role_consensus) == {"istituzionale", "economico"}


def test_branch_intensity_is_intra_role_consensus():
    """A branch's intensity is that Role's intra-Role Consensus (task-02 per-Role):
    a Role whose voters all chose the same Vocazione reads 1.0; a Role split across
    distinct Vocazioni reads lower."""
    state = _closed(
        ("u1", "istituzionale", "residenziale"),
        ("u2", "istituzionale", "residenziale"),  # cohesive → 1.0
        ("u3", "economico", "commerciale"),
        ("u4", "economico", "verde"),             # split → < 1.0
    )

    outcome = build_outcome(state)

    assert outcome.per_role_consensus["istituzionale"] == 1.0
    assert outcome.per_role_consensus["economico"] < 1.0


def test_consenso_totale_is_pooled_overall_not_mean_of_branches():
    """The "consenso totale" below the radar is the Consensus on the POOLED Votes,
    not the average of the branches. Two Roles each internally unanimous but on
    DIFFERENT Vocazioni: every branch reads 1.0, yet pooled the group is split."""
    state = _closed(
        ("u1", "istituzionale", "residenziale"),
        ("u2", "istituzionale", "residenziale"),
        ("u3", "economico", "commerciale"),
        ("u4", "economico", "commerciale"),
    )

    outcome = build_outcome(state)

    branches = outcome.per_role_consensus
    assert branches["istituzionale"] == 1.0 and branches["economico"] == 1.0
    mean_of_branches = sum(branches.values()) / len(branches)
    assert outcome.overall_consensus < mean_of_branches


def test_outcome_carries_n_and_round_number_for_persistence():
    """The ``round_outcomes`` row keys off the Bene and the Round ordinal and pins N
    (the frozen denominator) alongside the raw counts — so the measure is
    re-derivable offline and trends are analysable."""
    state = _closed(
        ("u1", "istituzionale", "residenziale"),
        ("u2", "economico", "commerciale"),
        ("u3", "tecnico", "verde"),
    )

    outcome = build_outcome(state)

    assert outcome.poi_id == "bene-1"
    assert outcome.round_number == 1
    assert outcome.n == 3


# --- Acceptance test (outer tracer): close → recap → new round ---------------


def test_closed_round_recaps_then_reopens_a_new_round():
    """Phase 3 end-to-end over the pure core: a Round of three voters in two Roles
    closes; ``build_outcome`` yields the radar (branches = Roles present, intensity =
    intra-Role Consensus), the pooled "consenso totale", and the raw counts + N for
    ``round_outcomes``. Closing then resets readiness, and the ready set re-opens a
    new Round through the same ready-gate, re-freezing N."""
    state = _closed(
        ("u1", "istituzionale", "residenziale"),
        ("u2", "economico", "commerciale"),
        ("u3", "economico", "commerciale"),
    )

    outcome = build_outcome(state)

    # Radar: a branch per Role present, each carrying its intra-Role Consensus.
    assert set(outcome.per_role_consensus) == {"istituzionale", "economico"}
    assert outcome.per_role_consensus["economico"] == pytest.approx(1.0)  # 2× commerciale
    # "consenso totale" is pooled (residenziale=1, commerciale=2), not the branch mean.
    assert outcome.overall_consensus == pytest.approx(0.4206198, abs=1e-6)
    # The round_outcomes payload: raw counts + frozen N.
    assert outcome.votes_by_role == {
        "istituzionale": {"residenziale": 1},
        "economico": {"commerciale": 2},
    }
    assert outcome.n == 3

    # Recap resets readiness — "inizia un nuovo round" starts its live count at 0.
    assert ready_count(state) == 0

    # The ready set re-opens a new Round through the same ready-gate (re-frozen N=2).
    state, _ = apply(state, Ready("u1"))
    state, _ = apply(state, Ready("u2"))
    state, effects = apply(state, OpenRound())

    assert state.round_number == 2
    assert state.phase == "voting"
    assert set(state.roster) == {"u1", "u2"}
    assert effects == [RoundOpened(poi_id="bene-1", round_number=2, n=2)]
