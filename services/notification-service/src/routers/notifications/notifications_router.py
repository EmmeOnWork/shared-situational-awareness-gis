"""The realtime router — thin glue over the Connection Hub.

Two public surfaces, no domain logic of its own:

* a **WebSocket** endpoint clients subscribe to: it verifies the handshake JWT
  (`?access_token=` or `access_token` subprotocol), then registers the connection
  on connect and unregisters it on disconnect (so a gone client receives no
  further broadcasts). An unauthorized handshake is refused before registration.
* `POST /notifications/publish`: validates a Notification (FastAPI rejects an
  invalid one with 422 before this body runs) and hands it to the Hub, which fans
  it to every connected client. The server broadcasts **globally** — no rooms —
  and an undelivered Notification is lost by design.

The module-level Hub is the single shared fan-out for the process.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from src.notifier.connection_hub import ConnectionHub
from src.notifier.notification import Notification
from src.notifier.ws_auth import TOKEN_SUBPROTOCOL, verify_handshake_token
from src.security.jwt_utils import TokenValidationError

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])

# One process-wide fan-out: every WS subscriber registers here and every publish
# reaches them through it.
hub = ConnectionHub()


@notifications_router.websocket("/ws")
async def subscribe(websocket: WebSocket):
    """Subscribe a client to broadcasts for the life of the connection.

    The handshake must carry a valid monolith JWT (ADR-0002) — as the
    ``?access_token=`` query param or an ``access_token`` subprotocol pair. A
    missing or invalid token is refused before ``accept`` and never registered
    with the Hub, so an unauthorized client receives nothing."""
    offered_subprotocols = websocket.scope.get("subprotocols", [])
    try:
        verify_handshake_token(
            websocket.query_params.get("access_token"),
            offered_subprotocols,
        )
    except TokenValidationError:
        # Refuse the handshake without accepting it: 1008 = policy violation.
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Echo the token subprotocol back when the client used that path, as the WS
    # spec requires the server to confirm one of the offered subprotocols.
    accepted = (
        TOKEN_SUBPROTOCOL if TOKEN_SUBPROTOCOL in offered_subprotocols else None
    )
    await websocket.accept(subprotocol=accepted)
    hub.register(websocket)
    try:
        # The client never sends; we only need to detect disconnect to clean up.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.unregister(websocket)


@notifications_router.post("/publish")
async def publish(notification: Notification):
    """Fan one validated Notification out to every connected client.

    Returns how many connections it reached — 0 is a clean no-op (nothing stored
    or replayed)."""
    # `exclude_none=True`: an UNSCOPED Notification must go out WITHOUT a `scope`
    # key, not as `scope: null`. The client parser treats a present-but-null scope
    # as a malformed frame and drops the whole Notification (no toast, no sound),
    # so emitting `scope: null` would silently swallow every unscoped alert even
    # though `delivered` reports a healthy 1+.
    delivered = await hub.broadcast(notification.model_dump(exclude_none=True))
    return {"delivered": delivered}
