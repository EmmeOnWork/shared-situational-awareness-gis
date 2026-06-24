"""Unit tests for the RoomManager — the per-Bene realtime orchestrator.

The deep core behind the WebSocket route: it holds one in-memory room per Bene
(its ``ProcessState`` + the live connections), turns an authenticated client
message into an engine event, reacts to the lifecycle effects (records the open
time, and on close persists the ``round_outcomes`` row with the Round's duration),
and broadcasts the projected view to every connection in that room. Unit-tested
with fake connections, a fake outcomes repo and a controllable clock — no
WebSocket, no DB (cf. notification-service ``test_connection_hub.py``).
"""

import asyncio

from src.rooms.room_manager import RoomManager


class FakeConn:
    """A stand-in WebSocket: records every view it is sent."""

    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


class FlakyConn(FakeConn):
    """A connection that can be 'killed' so later sends raise like a gone WebSocket
    (Starlette's "Cannot call send once a close message has been sent.")."""

    def __init__(self):
        super().__init__()
        self.alive = True

    async def send_json(self, payload):
        if not self.alive:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')
        self.sent.append(payload)


class FakeRepo:
    """Captures persisted outcomes instead of writing the shared DB."""

    def __init__(self):
        self.saved = []

    def save_outcome(self, outcome, duration_seconds):
        self.saved.append((outcome, duration_seconds))


class FakeClock:
    """A monotonic clock the test advances by hand to assert Round duration."""

    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _manager():
    return RoomManager(repo=FakeRepo(), now=FakeClock())


def _run(coro):
    return asyncio.run(coro)


def test_connect_sends_current_view_snapshot():
    """A client connecting to a Bene's room is immediately sent the current view —
    it converges on the live phase without waiting for the next change."""
    rm = _manager()
    conn = FakeConn()

    _run(rm.connect("bene-1", conn))

    assert len(conn.sent) == 1
    assert conn.sent[0]["phase"] == "lobby"
    assert conn.sent[0]["poi_id"] == "bene-1"


def test_event_broadcasts_updated_view_to_all_connections():
    """An authenticated client's action (here a join) is applied to the room's
    state and the new view is fanned out to EVERY connection in that room."""
    rm = _manager()
    a, b = FakeConn(), FakeConn()
    _run(rm.connect("bene-1", a))
    _run(rm.connect("bene-1", b))

    _run(rm.handle("bene-1", a, "u1", {"type": "join"}, role="tecnico"))

    assert a.sent[-1]["participants"] == [{"user_id": "u1", "role": "tecnico", "ready": False}]
    assert b.sent[-1]["participants"] == [{"user_id": "u1", "role": "tecnico", "ready": False}]


def test_full_round_persists_outcome_with_duration_and_enters_recap():
    """Driving a Bene through join→ready→start→vote to a full N/N close persists the
    ``round_outcomes`` row once, with the elapsed Round duration, and the broadcast
    view enters the recap carrying the radar."""
    repo = FakeRepo()
    clock = FakeClock()
    rm = RoomManager(repo=repo, now=clock)
    conn = FakeConn()
    _run(rm.connect("bene-1", conn))

    for u, role in [("u1", "istituzionale"), ("u2", "economico")]:
        _run(rm.handle("bene-1", conn, u, {"type": "join"}, role=role))
        _run(rm.handle("bene-1", conn, u, {"type": "ready"}))
    clock.t = 100.0
    _run(rm.handle("bene-1", conn, "u1", {"type": "start"}))  # opens the Round at t=100
    _run(rm.handle("bene-1", conn, "u1", {"type": "vote", "vocazione": "residenziale"}))
    clock.t = 142.5
    _run(rm.handle("bene-1", conn, "u2", {"type": "vote", "vocazione": "commerciale"}))  # N/N

    assert len(repo.saved) == 1
    outcome, duration = repo.saved[0]
    assert outcome.n == 2
    assert duration == 42.5
    assert conn.sent[-1]["phase"] == "recap"
    assert {b["role"] for b in conn.sent[-1]["recap"]["radar"]} == {"istituzionale", "economico"}


def test_unanimous_close_persists_final_outcome_and_broadcasts_phase4():
    """A unanimous N/N close is the terminal moment: the room still persists the final
    ``round_outcomes`` row (with the Round's duration, so the winner + timings are in
    the durable history) and the broadcast view enters phase 4 carrying the winning
    Vocazione and the number of Rounds — not the recap radar."""
    repo = FakeRepo()
    clock = FakeClock()
    rm = RoomManager(repo=repo, now=clock)
    conn = FakeConn()
    _run(rm.connect("bene-1", conn))

    for u, role in [("u1", "istituzionale"), ("u2", "economico")]:
        _run(rm.handle("bene-1", conn, u, {"type": "join"}, role=role))
        _run(rm.handle("bene-1", conn, u, {"type": "ready"}))
    clock.t = 10.0
    _run(rm.handle("bene-1", conn, "u1", {"type": "start"}))  # opens at t=10
    _run(rm.handle("bene-1", conn, "u1", {"type": "vote", "vocazione": "residenziale"}))
    clock.t = 25.0
    _run(rm.handle("bene-1", conn, "u2", {"type": "vote", "vocazione": "residenziale"}))  # N/N unanimous

    # The final Round's outcome is persisted with its duration (winner derivable:
    # votes_by_role is all 'residenziale', round_number = total rounds).
    assert len(repo.saved) == 1
    outcome, duration = repo.saved[0]
    assert duration == 15.0
    assert outcome.overall_consensus == 1.0
    # The broadcast is the phase-4 consensus-reached screen.
    assert conn.sent[-1]["phase"] == "consensus"
    assert conn.sent[-1]["consensus"] == {"winner": "residenziale", "rounds": 1}
    # The terminal phase ALSO carries the recap radar now (same visual as the recap,
    # but the widget offers no "continue") — unanimous ⇒ every Role at full consensus.
    assert conn.sent[-1]["recap"] is not None
    assert conn.sent[-1]["recap"]["overall"] == 1.0


def test_invalid_action_errors_only_the_offending_connection():
    """An engine-rejected action (here voting before any Round is open) is reported
    back to that one client as an error and does NOT broadcast or crash the room."""
    rm = _manager()
    a, b = FakeConn(), FakeConn()
    _run(rm.connect("bene-1", a))
    _run(rm.connect("bene-1", b))
    before_b = len(b.sent)

    _run(rm.handle("bene-1", a, "u1", {"type": "vote", "vocazione": "residenziale"}))

    assert a.sent[-1]["type"] == "error"
    assert len(b.sent) == before_b  # the other client saw no broadcast


def test_rooms_are_isolated_per_bene():
    """Each Bene has its own room: an event in one Bene never reaches another Bene's
    connections (every per-Bene structure keys off the Active Workshop)."""
    rm = _manager()
    a = FakeConn()  # in bene-1
    b = FakeConn()  # in bene-2
    _run(rm.connect("bene-1", a))
    _run(rm.connect("bene-2", b))
    before_b = len(b.sent)

    _run(rm.handle("bene-1", a, "u1", {"type": "join"}, role="tecnico"))

    assert a.sent[-1]["participants"]  # bene-1 updated
    assert len(b.sent) == before_b  # bene-2 untouched


def test_broadcast_survives_a_dead_connection_and_prunes_it():
    """A send to a connection that has gone away (a reconnect / refresh race) must not
    break the fan-out to the healthy connections nor crash the caller — otherwise the
    exception propagates out of ``handle`` and tears down the triggering client's
    socket, silently stopping its live updates. The dead connection is dropped."""
    rm = _manager()
    alive, flaky = FakeConn(), FlakyConn()
    _run(rm.connect("bene-1", alive, "u1"))
    _run(rm.connect("bene-1", flaky, "u2"))  # healthy at connect time
    flaky.alive = False  # its tab went away before the next broadcast

    # An action from the alive client broadcasts to both; the dead send must be
    # swallowed and the healthy client still updated.
    _run(rm.handle("bene-1", alive, "u1", {"type": "join"}, role="tecnico"))
    assert alive.sent[-1]["participants"][0]["user_id"] == "u1"

    # The dead connection was pruned, so a later broadcast still reaches the alive one
    # (and never retries the gone socket).
    _run(rm.handle("bene-1", alive, "u1", {"type": "ready"}))
    assert alive.sent[-1]["ready_count"] == 1


def _open_round_two_ready(rm, conn_by_user):
    """Drive a Bene to an open Round 1 with the given {user_id: connection} ready."""
    for user_id, conn in conn_by_user.items():
        _run(rm.connect("bene-1", conn, user_id))
    for user_id, conn in conn_by_user.items():
        _run(rm.handle("bene-1", conn, user_id, {"type": "join"}, role="tecnico"))
        _run(rm.handle("bene-1", conn, user_id, {"type": "ready"}))
    first = next(iter(conn_by_user))
    _run(rm.handle("bene-1", conn_by_user[first], first, {"type": "start"}))


def test_chat_unlocks_after_voting_and_broadcasts_anonymously():
    """A roster member who has voted may post to the Chat; the message is re-broadcast
    carrying only the Round number + body (never an author), and a participant who has
    NOT voted does not receive the Chat content at all — vote independence enforced at
    the wire, not just in the UI."""
    rm = _manager()
    voter, watcher = FakeConn(), FakeConn()
    _open_round_two_ready(rm, {"u1": voter, "u2": watcher})
    _run(rm.handle("bene-1", voter, "u1", {"type": "vote", "vocazione": "residenziale"}))

    _run(rm.handle("bene-1", voter, "u1", {"type": "chat", "body": "  io voto residenziale  "}))

    msg = voter.sent[-1]["chat"][-1]
    assert msg["body"] == "io voto residenziale"  # trimmed
    assert msg["round_number"] == 1
    assert "author_id" not in msg and "author" not in msg
    assert watcher.sent[-1]["chat"] == []  # u2 has not voted → sees no Chat


def test_chat_post_before_voting_is_rejected_and_not_broadcast():
    """The store's write-gate is enforced at the room edge: a member who has not voted
    cannot post — the sender alone gets an error, no one else sees a broadcast."""
    rm = _manager()
    a, b = FakeConn(), FakeConn()
    _open_round_two_ready(rm, {"u1": a, "u2": b})
    before_b = len(b.sent)

    _run(rm.handle("bene-1", a, "u1", {"type": "chat", "body": "prima di votare"}))

    assert a.sent[-1] == {
        "type": "error",
        "detail": "cannot post before voting this Round: 'u1'",
    }
    assert len(b.sent) == before_b


def test_chat_is_readable_in_recap_but_read_only():
    """Once the Round closes the Chat is readable by everyone in the recap, but a post
    is rejected (read-only in phase 3) and errors only the sender."""
    rm = _manager()
    a, b = FakeConn(), FakeConn()
    _open_round_two_ready(rm, {"u1": a, "u2": b})
    _run(rm.handle("bene-1", a, "u1", {"type": "vote", "vocazione": "residenziale"}))
    _run(rm.handle("bene-1", a, "u1", {"type": "chat", "body": "ci penso"}))
    _run(rm.handle("bene-1", b, "u2", {"type": "vote", "vocazione": "commerciale"}))  # N/N → recap

    assert b.sent[-1]["phase"] == "recap"
    assert [m["body"] for m in b.sent[-1]["chat"]] == ["ci penso"]  # readable now

    before_a = len(a.sent)
    _run(rm.handle("bene-1", a, "u1", {"type": "chat", "body": "troppo tardi"}))

    assert a.sent[-1]["type"] == "error"  # read-only in recap
    assert len(a.sent) == before_a + 1  # only the error, no broadcast

    msg = "empty chat message → rejected without touching the log"
    _run(rm.handle("bene-1", a, "u1", {"type": "chat", "body": "   "}))
    assert a.sent[-1] == {"type": "error", "detail": "messaggio vuoto"}, msg
