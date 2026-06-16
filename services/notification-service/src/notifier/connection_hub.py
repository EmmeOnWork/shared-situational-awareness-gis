"""The Connection Hub: an in-memory fan-out over live connections.

Deep core of the realtime pipe with a tiny surface — `register`,
`unregister`, `broadcast`. It holds a set of duck-typed connection objects
(anything with async `send_json`) and reaches every currently-registered one.
Nothing is persisted and nothing is replayed: a payload published to zero
connections is simply gone (fire-and-forget, CONTEXT.md). No FastAPI dependency
so it is unit-testable with fake connections.
"""


class ConnectionHub:
    def __init__(self):
        self._connections = set()

    def register(self, connection):
        self._connections.add(connection)

    def unregister(self, connection):
        self._connections.discard(connection)

    async def broadcast(self, payload):
        # Snapshot the set: a connection could unregister mid-iteration, and we
        # report reach over the connections live at the moment of broadcast.
        reached = list(self._connections)
        for connection in reached:
            await connection.send_json(payload)
        return len(reached)
