"""RoomManager — the per-Bene realtime orchestrator.

The deep core behind the WebSocket route. It owns one in-memory ``Room`` per Bene
(its ``ProcessState`` and the live connections), translates an **authenticated**
client message into an engine event, reacts to the lifecycle effects (records the
open time so the recap can report duration, and on ``RoundClosed`` persists the
``round_outcomes`` row via the injected repo), and broadcasts the projected
``RoundView`` to every connection in that room. The room's identity (``user_id``)
comes from the verified handshake, never from the message body.

IO is injected — ``repo`` (an ``OutcomesRepository``) and ``now`` (a clock) — so
the orchestration is unit-testable with fakes; the WebSocket route is the only
adapter that wires real connections, the real repo and ``time.monotonic``.
"""

from dataclasses import dataclass, field
from time import monotonic
from typing import Callable

from src.engine.recap import RoundOutcome, build_outcome
from src.engine.round_engine import (
    CastVote,
    ConsensusReached,
    DeclareRole,
    Join,
    OpenRound,
    ProcessState,
    Ready,
    RoundClosed,
    RoundOpened,
    apply,
    initial_state,
)
from src.engine.round_view import project_view


@dataclass
class Room:
    """A Bene's live room: its process state, open connections, the last recap
    outcome (so a client joining in the recap phase still sees the radar) and the
    monotonic timestamp the current Round opened at (for duration)."""

    state: ProcessState
    connections: set = field(default_factory=set)
    outcome: RoundOutcome | None = None
    opened_at: float | None = None


def _to_event(user_id: str, message: dict):
    """Map an authenticated client message to an engine event. ``user_id`` is the
    verified handshake identity, never trusted from the message body."""
    kind = message.get("type")
    if kind == "join":
        return Join(user_id)
    if kind == "declare_role":
        return DeclareRole(user_id, message["role"])
    if kind == "ready":
        return Ready(user_id)
    if kind == "start":
        return OpenRound()
    if kind == "vote":
        return CastVote(user_id, message["vocazione"])
    raise ValueError(f"unknown message type: {kind!r}")


class _NullNotifier:
    """No-op producer: the default when a RoomManager is built without a notifier
    (e.g. persistence-focused unit tests). Swallows every lifecycle effect."""

    async def react(self, effect) -> None:  # noqa: D401 — null object
        return None


class RoomManager:
    def __init__(self, repo, now: Callable[[], float] = monotonic, notifier=None):
        self._repo = repo
        self._now = now
        # The Notification producer (lifecycle effects → Realtime Notifier). Defaults
        # to a no-op so persistence-only tests need not wire one; the WS route injects
        # the real producer. Best-effort, exactly like ``repo``.
        self._notifier = notifier or _NullNotifier()
        self._rooms: dict[str, Room] = {}

    def _room(self, poi_id: str) -> Room:
        room = self._rooms.get(poi_id)
        if room is None:
            room = Room(state=initial_state(poi_id))
            self._rooms[poi_id] = room
        return room

    async def connect(self, poi_id: str, connection) -> None:
        """Register a connection and immediately send it the room's current view."""
        room = self._room(poi_id)
        room.connections.add(connection)
        await connection.send_json(self._view(room))

    def disconnect(self, poi_id: str, connection) -> None:
        """Drop a gone connection so it receives no further broadcasts."""
        room = self._rooms.get(poi_id)
        if room is not None:
            room.connections.discard(connection)

    async def handle(self, poi_id: str, connection, user_id: str, message: dict) -> None:
        """Apply one authenticated client message, react to its effects and
        broadcast the new view. An engine-rejected action is reported back to the
        sending ``connection`` alone and leaves the room (and every other client)
        unchanged."""
        room = self._room(poi_id)
        try:
            event = _to_event(user_id, message)
            state, effects = apply(room.state, event)
        except (ValueError, KeyError, NotImplementedError) as exc:
            await connection.send_json({"type": "error", "detail": str(exc)})
            return

        room.state = state
        for effect in effects:
            await self._react(room, effect)
        await self._broadcast(room)

    async def _react(self, room: Room, effect) -> None:
        """Turn a lifecycle effect into the IO at the edge: stamp the open time, on
        close build + persist the outcome with the Round's duration, and publish the
        shared lifecycle moment to the Realtime Notifier (Bene-scoped)."""
        if isinstance(effect, RoundOpened):
            room.opened_at = self._now()
            room.outcome = None
        elif isinstance(effect, (RoundClosed, ConsensusReached)):
            # Both close effects persist the final ``round_outcomes`` row with the
            # Round's duration. At the terminal ConsensusReached the winner + timings
            # thus land in the durable history (winner is derivable from the row's
            # unanimous distribution); no cross-context Bene→Vocazione link is written
            # (ADR-0003). The phase-4 view derives winner + rounds from the state.
            outcome = build_outcome(room.state)
            duration = None if room.opened_at is None else self._now() - room.opened_at
            room.outcome = outcome
            self._repo.save_outcome(outcome, duration)
        # The producer maps open/close/consensus to a Bene-scoped Notifier publish and
        # ignores everything else (a Vote emits no effect, so it never publishes).
        await self._notifier.react(effect)

    def _view(self, room: Room) -> dict:
        outcome = room.outcome if room.state.phase == "recap" else None
        return project_view(room.state, outcome=outcome)

    async def _broadcast(self, room: Room) -> None:
        view = self._view(room)
        for connection in list(room.connections):
            await connection.send_json(view)
