"""Tests for the Notification producer — lifecycle effects → Realtime Notifier.

The backend producer (PRD module 5) that maps the round engine's lifecycle
side-effects to publishes against the Realtime Notifier's ingress, each carrying
the Bene **Scope** ``{axis:"workshop", value: poiId}`` so only participants whose
Active Workshop is that Bene see the toast/hear the sound. A **Vote produces no
Notification** (confirming a Vote is purely local widget feedback) — and a
non-closing Vote emits no engine effect at all, so it never reaches the producer.

Exercised with a recording/fake Notifier client (asserting severity, scope,
count), the same way the RoomManager is unit-tested with fakes — no HTTP.
"""

import asyncio


class RecordingNotifierClient:
    """A stand-in Notifier client: records every Notification it is asked to
    publish instead of POSTing the real publish ingress."""

    def __init__(self):
        self.published = []

    async def publish(self, notification: dict) -> None:
        self.published.append(notification)


def _run(coro):
    return asyncio.run(coro)


# --- Inner: the mapping from one lifecycle effect to one publish -------------


def test_round_opened_publishes_info_scoped_to_the_bene():
    """A new Round opening ⇒ an ``info`` Notification scoped to the Bene's workshop
    axis, so only participants whose Active Workshop is that Bene are alerted."""
    from src.engine.round_engine import RoundOpened
    from src.notifications.notification_producer import NotificationProducer

    client = RecordingNotifierClient()
    producer = NotificationProducer(client)

    _run(producer.react(RoundOpened(poi_id="42", round_number=2, n=3)))

    assert len(client.published) == 1
    assert client.published[0]["severity"] == "info"
    assert client.published[0]["scope"] == {"axis": "workshop", "value": "42"}


def test_round_closed_publishes_info_scoped_to_the_bene():
    """A Round closing (everyone voted, N/N) ⇒ an ``info`` Notification scoped to the
    Bene — the same severity as opening, a routine shared lifecycle moment."""
    from src.engine.round_engine import RoundClosed
    from src.notifications.notification_producer import NotificationProducer

    client = RecordingNotifierClient()

    _run(NotificationProducer(client).react(RoundClosed(poi_id="7", round_number=1, n=4)))

    assert len(client.published) == 1
    assert client.published[0]["severity"] == "info"
    assert client.published[0]["scope"] == {"axis": "workshop", "value": "7"}


def test_consensus_reached_publishes_success_scoped_to_the_bene():
    """Consensus reached (the terminal, celebrated moment) ⇒ a ``success``
    Notification — distinct from the routine ``info`` of opening/closing — still
    Bene-scoped."""
    from src.engine.round_engine import ConsensusReached
    from src.notifications.notification_producer import NotificationProducer

    client = RecordingNotifierClient()

    _run(
        NotificationProducer(client).react(
            ConsensusReached(poi_id="9", round_number=3, winner="residenziale", rounds=3)
        )
    )

    assert len(client.published) == 1
    assert client.published[0]["severity"] == "success"
    assert client.published[0]["scope"] == {"axis": "workshop", "value": "9"}


def test_an_unmapped_effect_publishes_nothing():
    """An effect that is not a shared lifecycle moment maps to no Notification, so the
    producer makes no publish call (the guard behind 'a Vote produces no Notification':
    anything that isn't open/close/consensus stays silent)."""
    from src.notifications.notification_producer import NotificationProducer

    client = RecordingNotifierClient()

    _run(NotificationProducer(client).react(object()))

    assert client.published == []


# --- Acceptance (outer tracer): the producer wired into the RoomManager ------


class _FakeConn:
    async def send_json(self, payload):
        pass


class _FakeRepo:
    def save_outcome(self, outcome, duration_seconds):
        pass


def test_full_round_publishes_scoped_lifecycle_notifications_not_votes():
    """Driving a Bene through join→ready→start→vote→(N/N) close publishes exactly the
    shared lifecycle moments to the Notifier — a ``RoundOpened`` (info) on start and a
    ``RoundClosed`` (info) on the close — each Bene-scoped, and the intermediate
    non-closing Vote publishes nothing (a Vote is purely local widget feedback)."""
    from src.notifications.notification_producer import NotificationProducer
    from src.rooms.room_manager import RoomManager

    client = RecordingNotifierClient()
    rm = RoomManager(repo=_FakeRepo(), notifier=NotificationProducer(client))
    conn = _FakeConn()
    _run(rm.connect("42", conn))

    for u, role in [("u1", "istituzionale"), ("u2", "economico")]:
        _run(rm.handle("42", conn, u, {"type": "join"}))
        _run(rm.handle("42", conn, u, {"type": "declare_role", "role": role}))
        _run(rm.handle("42", conn, u, {"type": "ready"}))
    _run(rm.handle("42", conn, "u1", {"type": "start"}))  # → RoundOpened
    after_open = len(client.published)
    _run(rm.handle("42", conn, "u1", {"type": "vote", "vocazione": "residenziale"}))
    assert len(client.published) == after_open  # a non-closing Vote publishes nothing
    _run(rm.handle("42", conn, "u2", {"type": "vote", "vocazione": "commerciale"}))  # N/N close

    severities = [n["severity"] for n in client.published]
    scopes = [n["scope"] for n in client.published]
    assert severities == ["info", "info"]  # RoundOpened, RoundClosed — no Vote between
    assert all(s == {"axis": "workshop", "value": "42"} for s in scopes)
