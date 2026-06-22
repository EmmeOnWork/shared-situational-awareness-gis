"""Round engine — pure-core state machine (lobby / phase 0).

A deep, IO-free reducer over a Bene's consensus process. ``apply(state, event)``
returns the next ``ProcessState`` and the lifecycle side-effects to emit; the room
manager and persistence layers (not this module) turn those into WebSocket fan-out,
DB writes and Notifier publishes. This slice (task 03) covers the lobby events that
form the roster and open Round 1 through the ready-gate — ``Join``, ``DeclareRole``,
``Ready``, ``OpenRound`` — freezing N at the ready set (service ADR-0001).
"""

from dataclasses import dataclass, field, replace

# The small stakeholder-Role catalog the service owns (radar branches; the grouping
# for intra-Role Consensus). Distinct from the JWT auth ``role`` and not carried in
# the token — a Participant self-declares one of these at join.
ROLE_CATALOG = ("istituzionale", "economico", "tecnico", "sociale", "ambientale")


@dataclass(frozen=True)
class Participant:
    user_id: str
    role: str | None = None
    ready: bool = False


@dataclass(frozen=True)
class ProcessState:
    """A Bene's round process. ``round_number == 0`` is the lobby (no Round open
    yet); ``roster`` is the frozen ready set of the currently open Round."""

    poi_id: str
    participants: tuple[Participant, ...] = ()
    round_number: int = 0
    roster: tuple[str, ...] = ()
    phase: str = "lobby"
    # The open Round's ballots: roster user_id → chosen Vocazione. Reset each
    # OpenRound; a Vote is immutable within the Round (final on confirmation).
    votes: dict = field(default_factory=dict)


# --- Lobby events ------------------------------------------------------------


@dataclass(frozen=True)
class Join:
    user_id: str


@dataclass(frozen=True)
class DeclareRole:
    user_id: str
    role: str


@dataclass(frozen=True)
class Ready:
    user_id: str


@dataclass(frozen=True)
class OpenRound:
    pass


@dataclass(frozen=True)
class CastVote:
    user_id: str
    vocazione: str


# --- Side-effects ------------------------------------------------------------


@dataclass(frozen=True)
class RoundOpened:
    poi_id: str
    round_number: int
    n: int


@dataclass(frozen=True)
class RoundClosed:
    poi_id: str
    round_number: int
    n: int


@dataclass(frozen=True)
class ConsensusReached:
    """The terminal lifecycle moment (phase 4): the closing Round was unanimous, so
    overall Consensus = 100%. Carries the ``winner`` Vocazione the group converged on
    and ``rounds`` (how many it took = the closing Round's ordinal). Replaces
    ``RoundClosed`` at the terminal close — it is a distinct, celebrated moment
    (Notifier ``success``, not the round-closed ``info``)."""

    poi_id: str
    round_number: int
    winner: str
    rounds: int


def initial_state(poi_id: str) -> ProcessState:
    """An empty lobby for a Bene: no participants, no Round open."""
    return ProcessState(poi_id=poi_id)


def _find(state: ProcessState, user_id: str) -> Participant | None:
    return next((p for p in state.participants if p.user_id == user_id), None)


def apply(state: ProcessState, event) -> tuple[ProcessState, list]:
    """Reduce one lobby event into the next state and its emitted side-effects."""
    if isinstance(event, Join):
        if _find(state, event.user_id) is not None:
            return state, []
        joined = state.participants + (Participant(user_id=event.user_id),)
        return replace(state, participants=joined), []

    if isinstance(event, DeclareRole):
        if event.role not in ROLE_CATALOG:
            raise ValueError(f"unknown stakeholder Role: {event.role!r}")
        return _update_participant(
            state, event.user_id, lambda p: replace(p, role=event.role)
        ), []

    if isinstance(event, Ready):
        return _update_participant(
            state, event.user_id, lambda p: replace(p, ready=True)
        ), []

    if isinstance(event, OpenRound):
        if state.phase == "consensus":
            raise ValueError("consensus reached — the process is terminal")
        roster = tuple(p.user_id for p in state.participants if p.ready)
        if not roster:
            raise ValueError("cannot open a Round with nobody ready")
        opened = replace(
            state,
            round_number=state.round_number + 1,
            roster=roster,
            phase="voting",
            votes={},
        )
        return opened, [
            RoundOpened(
                poi_id=state.poi_id,
                round_number=opened.round_number,
                n=len(roster),
            )
        ]

    if isinstance(event, CastVote):
        if event.user_id not in state.roster:
            raise ValueError(f"not in this Round's roster: {event.user_id!r}")
        if event.user_id in state.votes:
            raise ValueError(f"Vote already cast this Round: {event.user_id!r}")
        voted = {**state.votes, event.user_id: event.vocazione}
        if len(voted) < len(state.roster):
            return replace(state, votes=voted), []
        # The last (N/N) Vote closes the Round for everyone — full presence-
        # unanimity, no timeout/quorum (CONTEXT; ADR-0001). Consensus + the recap
        # outcome are computed by recap.build_outcome off the close effect.
        # Ready flags reset so the next Round opens through the same phase-3
        # ready-gate ("pronti a ricominciare") rather than re-firing the old set.
        unready = tuple(replace(p, ready=False) for p in state.participants)
        ballots = set(voted.values())
        if len(ballots) == 1:
            # Everyone voted the SAME Vocazione → overall Consensus = 100% (zero
            # entropy, ADR-0002). This is the terminal state (phase 4): the process
            # stops here, no further Round opens, and a single ConsensusReached
            # carries the winner + how many Rounds it took. (n=1 is trivially
            # unanimous — one Participant settles it.)
            settled = replace(state, participants=unready, votes=voted, phase="consensus")
            return settled, [
                ConsensusReached(
                    poi_id=state.poi_id,
                    round_number=state.round_number,
                    winner=next(iter(ballots)),
                    rounds=state.round_number,
                )
            ]
        closed = replace(state, participants=unready, votes=voted, phase="recap")
        return closed, [
            RoundClosed(
                poi_id=state.poi_id,
                round_number=state.round_number,
                n=len(state.roster),
            )
        ]

    raise NotImplementedError(f"unhandled event: {event!r}")


def voted_count(state: ProcessState) -> int:
    """How many roster members have cast their Vote — the live 'X' in 'X/N hanno
    votato' the room fans out the instant anyone votes."""
    return len(state.votes)


def remaining_count(state: ProcessState) -> int:
    """How many roster members are still to vote — the '(N−X)' a voter sees as
    'rimasti'; reaches 0 exactly when the Round closes (N/N)."""
    return len(state.roster) - len(state.votes)


def ready_count(state: ProcessState) -> int:
    """How many lobby Participants are ready to start — the live count the lobby
    fans out so clients begin together rather than prematurely."""
    return sum(1 for p in state.participants if p.ready)


def _update_participant(state, user_id, change):
    """Return ``state`` with the matching participant replaced by ``change(p)``."""
    return replace(
        state,
        participants=tuple(
            change(p) if p.user_id == user_id else p for p in state.participants
        ),
    )
