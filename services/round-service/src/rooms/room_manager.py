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
from datetime import datetime, timezone
from time import monotonic
from typing import Callable

from src.chat.chat_store import (
    ChatLog,
    append as chat_append,
    empty_chat,
    read as chat_read,
)
from src.engine.recap import RoundOutcome, build_outcome
from src.engine.round_engine import (
    CastVote,
    ConsensusReached,
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


def _utcnow() -> datetime:
    """Wall-clock UTC for Chat timestamps — distinct from the monotonic ``now`` the
    room uses for Round durations (which must be gap-free, not wall-clock)."""
    return datetime.now(timezone.utc)


@dataclass
class Room:
    """A Bene's live room: its process state, the anonymous Chat log (continuous
    across all the Bene's Rounds), the open connections mapped to their handshake
    ``user_id`` (so each can be sent a Chat view gated on whether *they* have voted),
    the last recap outcome (so a client joining in the recap phase still sees the
    radar) and the monotonic timestamp the current Round opened at (for duration)."""

    state: ProcessState
    chat: ChatLog
    members: dict = field(default_factory=dict)  # connection -> user_id
    outcome: RoundOutcome | None = None
    opened_at: float | None = None


def _to_event(user_id: str, role: str | None, message: dict):
    """Map an authenticated client message to an engine event. ``user_id`` and the
    stakeholder ``role`` are the verified handshake identity (JWT ``sub`` +
    ``stakeholder_role`` claim), never trusted from the message body — so ``join``
    carries the account's Role with no separate declaration step."""
    kind = message.get("type")
    if kind == "join":
        return Join(user_id, role)
    if kind == "ready":
        return Ready(user_id)
    if kind == "start":
        return OpenRound()
    if kind == "vote":
        return CastVote(user_id, message["vocazione"])
    raise ValueError(f"unknown message type: {kind!r}")


def _chat_visible(state: ProcessState, user_id: str | None) -> bool:
    """Who may READ the Chat. Mirrors the store's WRITE gate so no one can read
    others' arguments before voting (Vote independence): during ``voting`` only a
    participant who has already cast their Vote sees it; in the ``recap`` AND the
    terminal ``consensus`` phase everyone does (the Round is closed, all Votes are in —
    the deliberation log is read-only). Hidden in the lobby."""
    if state.phase in ("recap", "consensus"):
        return True
    if state.phase == "voting":
        return user_id is not None and user_id in state.votes
    return False


class _NullNotifier:
    """No-op producer: the default when a RoomManager is built without a notifier
    (e.g. persistence-focused unit tests). Swallows every lifecycle effect."""

    async def react(self, effect) -> None:  # noqa: D401 — null object
        return None


class RoomManager:
    def __init__(
        self,
        repo,
        now: Callable[[], float] = monotonic,
        notifier=None,
        chat_now: Callable[[], datetime] = _utcnow,
    ):
        self._repo = repo
        self._now = now
        # Wall-clock for Chat message timestamps (injectable for tests); separate
        # from the monotonic ``now`` used for Round durations.
        self._chat_now = chat_now
        # The Notification producer (lifecycle effects → Realtime Notifier). Defaults
        # to a no-op so persistence-only tests need not wire one; the WS route injects
        # the real producer. Best-effort, exactly like ``repo``.
        self._notifier = notifier or _NullNotifier()
        self._rooms: dict[str, Room] = {}

    def _room(self, poi_id: str) -> Room:
        room = self._rooms.get(poi_id)
        if room is None:
            room = Room(state=initial_state(poi_id), chat=empty_chat(poi_id))
            self._rooms[poi_id] = room
        return room

    async def connect(self, poi_id: str, connection, user_id: str | None = None) -> None:
        """Register a connection (under its handshake ``user_id``) and immediately send
        it the room's current view, gated to that user (so the Chat is hidden until
        they have voted)."""
        room = self._room(poi_id)
        room.members[connection] = user_id
        await connection.send_json(self._view(room, user_id))

    def disconnect(self, poi_id: str, connection) -> None:
        """Drop a gone connection so it receives no further broadcasts."""
        room = self._rooms.get(poi_id)
        if room is not None:
            room.members.pop(connection, None)

    async def handle(
        self,
        poi_id: str,
        connection,
        user_id: str,
        message: dict,
        role: str | None = None,
    ) -> None:
        """Apply one authenticated client message, react to its effects and
        broadcast the new view. ``role`` is the sender's stakeholder Role from the
        verified handshake (used by ``join``). An engine-rejected action is reported
        back to the sending ``connection`` alone and leaves the room (and every other
        client) unchanged."""
        room = self._room(poi_id)
        # A Chat post is not an engine event (it never changes the ProcessState): it
        # is gated and appended to the Bene's Chat log separately, then re-broadcast.
        if message.get("type") == "chat":
            await self._handle_chat(room, connection, user_id, message)
            return
        try:
            event = _to_event(user_id, role, message)
            state, effects = apply(room.state, event)
        except (ValueError, KeyError, NotImplementedError) as exc:
            await connection.send_json({"type": "error", "detail": str(exc)})
            return

        room.state = state
        for effect in effects:
            await self._react(room, effect)
        await self._broadcast(room)

    async def _handle_chat(self, room: Room, connection, user_id: str, message: dict) -> None:
        """Append one anonymous Chat message, gated by the store on the current state
        (the author must have voted this Round). A rejected post errors only the
        sender; a successful one re-broadcasts so the message appears live for every
        eligible reader."""
        body = message.get("body")
        if not isinstance(body, str) or not body.strip():
            await connection.send_json({"type": "error", "detail": "messaggio vuoto"})
            return
        try:
            log, _effects = chat_append(
                room.chat, room.state, user_id, body.strip(), now=self._chat_now()
            )
        except ValueError as exc:
            await connection.send_json({"type": "error", "detail": str(exc)})
            return
        room.chat = log
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

    def _view(self, room: Room, user_id: str | None) -> dict:
        """Project the room for one recipient. The recap radar (the saved ``outcome``)
        is carried in BOTH the recap and the terminal consensus phase, so the consensus
        screen is the same as the recap (minus any 'continue'). The Chat is included
        only when that recipient may read it (post-vote / recap / consensus); everyone
        else gets an empty Chat, so vote independence holds at the wire, not just the UI."""
        outcome = room.outcome if room.state.phase in ("recap", "consensus") else None
        chat = chat_read(room.chat) if _chat_visible(room.state, user_id) else ()
        return project_view(room.state, outcome=outcome, chat=chat)

    async def _broadcast(self, room: Room) -> None:
        """Fan out a per-recipient view to every connection (each sees the Chat only
        if eligible — hence one projection per member, not one shared view).

        A send to a connection that has gone away (a reconnect / refresh / Bene-switch
        race can leave a stale member for an instant) must NEVER break the fan-out to
        the healthy connections nor crash the caller — that would propagate out of
        ``handle``, tear down the *triggering* client's socket and silently stop its
        live updates. So a failed send just drops that connection from the room."""
        dead = []
        for connection, user_id in list(room.members.items()):
            try:
                await connection.send_json(self._view(room, user_id))
            except Exception:  # noqa: BLE001 — a gone connection must not break the room
                dead.append(connection)
        for connection in dead:
            room.members.pop(connection, None)
