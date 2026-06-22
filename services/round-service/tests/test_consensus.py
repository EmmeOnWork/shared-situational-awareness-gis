"""Unit tests for the pure Consensus calculator (service ADR-0002).

Pure-function-in-isolation style (cf. reuse-service ``test_bene_list_builder.py``):
no TestClient, no DB — feed vote counts by Role × Vocazione, assert the measure's
defining properties and a hand-derived worked fixture.
"""

import pytest

from src.consensus.consensus import compute_consensus


# --- Inner unit cycles --------------------------------------------------------


def test_unanimity_gives_one():
    """A Role whose voters all chose the same Vocazione is fully cohesive ⇒ C = 1."""
    res = compute_consensus({"economico": {"residenziale": 4}}, k=16)

    assert res.per_role["economico"] == pytest.approx(1.0)


def test_maximal_realisable_dispersion_gives_zero():
    """Each of n≤k voters picked a distinct Vocazione — the most spread a group of
    that size can reach. Normalising by the realisable max ln(min(n,k)) ⇒ C = 0."""
    res = compute_consensus(
        {"tecnico": {"a": 1, "b": 1, "c": 1, "d": 1}}, k=16
    )

    assert res.per_role["tecnico"] == pytest.approx(0.0)


def test_singleton_level_gives_one():
    """A Role of one voter is trivially unanimous; the realisable max ln(min(1,k))=0
    is undefined, so a singleton level is defined as C = 1 (ADR-0002)."""
    res = compute_consensus({"istituzionale": {"residenziale": 1}}, k=16)

    assert res.per_role["istituzionale"] == pytest.approx(1.0)


def test_overall_is_pooled_not_mean_of_roles():
    """Overall Consensus is the measure on the POOLED votes, not the average of the
    per-Role values. Two Roles each internally unanimous but on DIFFERENT Vocazioni:
    every branch reads C=1, yet pooled the group is split ⇒ overall < 1."""
    votes = {
        "istituzionale": {"residenziale": 3},
        "economico": {"commerciale": 3},
    }

    res = compute_consensus(votes, k=16)

    assert res.per_role["istituzionale"] == pytest.approx(1.0)
    assert res.per_role["economico"] == pytest.approx(1.0)
    mean_of_branches = sum(res.per_role.values()) / len(res.per_role)
    assert mean_of_branches == pytest.approx(1.0)
    # pooled residenziale=3, commerciale=3, n=6: 1 − ln2/ln(min(6,16))
    assert res.overall == pytest.approx(0.6131472, abs=1e-6)
    assert res.overall < mean_of_branches


def test_monotonic_under_concentration_toward_mode():
    """Moving a Vote from a minority Vocazione onto the mode tightens the group ⇒
    Consensus strictly increases."""
    spread = compute_consensus({"economico": {"residenziale": 3, "commerciale": 2}})
    concentrated = compute_consensus({"economico": {"residenziale": 4, "commerciale": 1}})

    assert concentrated.per_role["economico"] > spread.per_role["economico"]


def test_consensus_stays_within_unit_interval():
    """Per-Role and overall Consensus are always in [0,1] for arbitrary counts."""
    votes = {
        "istituzionale": {"residenziale": 5, "verde": 2},
        "economico": {"commerciale": 1, "residenziale": 1, "verde": 1, "logistica": 4},
        "tecnico": {"verde": 3},
    }

    res = compute_consensus(votes, k=16)

    for c in res.per_role.values():
        assert 0.0 <= c <= 1.0
    assert 0.0 <= res.overall <= 1.0


# --- Acceptance test (worked fixture from the grilling example) ---------------


def test_worked_fixture_nine_participants_three_roles():
    """9 participants in 3 Roles of 3. Per-Role and overall Consensus match values
    derived by hand from C = 1 − H/ln(min(n,k)), and the overall is computed on the
    pooled votes — demonstrably NOT the mean of the per-Role branches."""
    votes = {
        "istituzionale": {"residenziale": 3},                              # unanimous
        "economico": {"residenziale": 2, "commerciale": 1},                # split 2/1
        "tecnico": {"residenziale": 1, "commerciale": 1, "verde": 1},      # uniform n=3
    }

    res = compute_consensus(votes, k=16)

    assert res.per_role["istituzionale"] == pytest.approx(1.0)
    assert res.per_role["economico"] == pytest.approx(0.4206198, abs=1e-6)
    assert res.per_role["tecnico"] == pytest.approx(0.0)

    # pooled: residenziale=6, commerciale=2, verde=1, n=9
    assert res.overall == pytest.approx(0.6137466, abs=1e-6)

    mean_of_branches = sum(res.per_role.values()) / len(res.per_role)
    assert res.overall != pytest.approx(mean_of_branches)
