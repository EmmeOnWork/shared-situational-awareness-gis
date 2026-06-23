"""Integration tests for the per-Bene WebSocket route (/rounds/ws/{poi_id}).

Drive the route through FastAPI's TestClient WS client: assert the handshake guard
(an unauthenticated connection is refused before it joins any room), that a verified
client is sent the current view on connect, and that an authenticated message is
applied and broadcast back. The room logic itself is unit-tested in
``test_room_manager.py``; these cover the adapter wiring (auth + connect + receive).

Each test uses a distinct poi_id so the process-wide RoomManager's in-memory rooms
do not leak between tests.
"""

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import make_token


def test_handshake_without_token_is_refused(client):
    """A WS handshake carrying no JWT is closed (1008) before joining a room — an
    unauthorized client never sees a Bene's state."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/rounds/ws/201") as ws:
            ws.receive_json()


def test_verified_client_receives_the_current_view_on_connect(client):
    """A handshake with a valid access token (via ?access_token=) is accepted and
    immediately sent the room's current view — the empty lobby for a fresh Bene."""
    token = make_token()
    with client.websocket_connect(f"/rounds/ws/202?access_token={token}") as ws:
        view = ws.receive_json()

    assert view["poi_id"] == 202
    assert view["phase"] == "lobby"
    assert view["participants"] == []


def test_authenticated_message_is_applied_and_broadcast(client):
    """A `join` message from a verified client is applied with the handshake identity
    (JWT sub) and the updated view is broadcast back over the same connection."""
    token = make_token(sub="7", stakeholder_role="economico")
    with client.websocket_connect(f"/rounds/ws/203?access_token={token}") as ws:
        ws.receive_json()  # the initial snapshot
        ws.send_json({"type": "join"})
        view = ws.receive_json()

    # The stakeholder Role is taken from the handshake token, not the message body.
    assert view["participants"] == [{"user_id": "7", "role": "economico", "ready": False}]
    assert view["ready_count"] == 0
