"""The Connection Hub — the in-memory relay, tested with fake connections.

No live WebSocket and no FastAPI: the Hub holds a set of duck-typed connection
objects (anything with async `send_json`) and fans a payload to all of them.
This is the deep core of the slice — register/unregister/broadcast — proven in
isolation so the router stays thin glue.
"""

import asyncio

from src.notifier.connection_hub import ConnectionHub


class FakeConnection:
    """A stand-in for a live WebSocket: records what the Hub sends it."""

    def __init__(self):
        self.received = []

    async def send_json(self, payload):
        self.received.append(payload)


def test_register_then_broadcast_reaches_connection():
    hub = ConnectionHub()
    conn = FakeConnection()
    hub.register(conn)

    asyncio.run(hub.broadcast({"title": "hello"}))

    assert conn.received == [{"title": "hello"}]


def test_unregister_stops_further_broadcasts():
    hub = ConnectionHub()
    conn = FakeConnection()
    hub.register(conn)
    hub.unregister(conn)

    asyncio.run(hub.broadcast({"title": "hello"}))

    assert conn.received == []


def test_broadcast_reaches_all_registered_and_none_unregistered():
    hub = ConnectionHub()
    a, b, gone = FakeConnection(), FakeConnection(), FakeConnection()
    hub.register(a)
    hub.register(b)
    hub.register(gone)
    hub.unregister(gone)

    asyncio.run(hub.broadcast({"n": 1}))

    assert a.received == [{"n": 1}]
    assert b.received == [{"n": 1}]
    assert gone.received == []


def test_broadcast_with_no_connections_is_a_clean_noop():
    """A publish with zero clients connected must not raise — it is simply lost,
    nothing is stored or replayed (fire-and-forget)."""
    hub = ConnectionHub()

    asyncio.run(hub.broadcast({"n": 1}))  # no assertion needed: must not raise


def test_broadcast_returns_the_number_of_connections_reached():
    """`broadcast` reports its reach so the publish ingress can echo it — 0 when
    nobody is connected, which is the no-op the producer sees."""
    hub = ConnectionHub()
    hub.register(FakeConnection())
    hub.register(FakeConnection())

    assert asyncio.run(hub.broadcast({"n": 1})) == 2
    hub_empty = ConnectionHub()
    assert asyncio.run(hub_empty.broadcast({"n": 1})) == 0
