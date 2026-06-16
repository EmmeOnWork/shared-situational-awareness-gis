"""Acceptance: the WebSocket is closed to unauthorized clients (slice 3).

Slice 2 left the WS pipe open to anyone. Now a handshake must carry a valid
monolith JWT (query param or subprotocol); a missing or invalid token is refused
and never registered with the Hub, so that client receives nothing. Exercised
through the public WS surface only — no knowledge of ws_auth/Hub internals.

ws-client reconnect/backoff and token-refresh-on-reconnect are connective glue,
verified manually per the task's testing decisions; they are not asserted here.
"""

import pytest
from starlette.websockets import WebSocketDisconnect

from tests.conftest import make_token

PUBLISH_URL = "/notifications/publish"
VALID = {"severity": "warning", "title": "Round chiuso", "body": "Tutti hanno votato"}


def test_handshake_with_invalid_token_is_rejected(client):
    """A bogus token never completes the handshake — the connection is refused,
    so the client is never registered and a later publish reaches it not at all."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/notifications/ws?access_token=not-a-real-jwt"
        ) as ws:
            ws.receive_json()


def test_handshake_with_missing_token_is_rejected(client):
    """No token at all is refused just like a bogus one — the pipe is closed by
    default, not open by default."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/notifications/ws") as ws:
            ws.receive_json()


def test_valid_token_in_query_param_connects_and_receives(client):
    """A valid JWT on the query string completes the handshake and the now-
    registered client receives a subsequently-published Notification."""
    with client.websocket_connect(
        f"/notifications/ws?access_token={make_token()}"
    ) as ws:
        resp = client.post(PUBLISH_URL, json=VALID)
        assert resp.status_code == 200

        received = ws.receive_json()

    assert received["title"] == "Round chiuso"


def test_valid_token_in_subprotocol_connects_and_receives(client):
    """A valid JWT carried as the ``access_token`` subprotocol pair completes the
    handshake and the registered client receives a published Notification."""
    with client.websocket_connect(
        "/notifications/ws",
        subprotocols=["access_token", make_token()],
    ) as ws:
        resp = client.post(PUBLISH_URL, json=VALID)
        assert resp.status_code == 200

        received = ws.receive_json()

    assert received["title"] == "Round chiuso"
