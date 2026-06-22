"""The per-Bene realtime WebSocket route — the Round Manager's live transport.

One room per Bene (``/rounds/ws/{poi_id}``): a client subscribes, is sent the
current view, then drives the process by sending authenticated messages (join,
declare_role, ready, start, vote) which the RoomManager applies and fans back out
to every connection in that Bene's room.

Mounted **unguarded** by ``app.py`` (unlike the HTTP data routes): a browser cannot
put a bearer token on a WS handshake, so this route self-guards via ``ws_auth`` —
the token rides ``?access_token=`` or the ``access_token`` subprotocol and is
verified with the same key the HTTP group uses. The identity (``user_id`` = JWT
``sub``) is taken from that verified handshake, never from the message body.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from src.notifications.notification_producer import NotificationProducer
from src.notifications.notifier_client import NotifierClient
from src.persistence.outcomes_repository import OutcomesRepository
from src.rooms.room_manager import RoomManager
from src.security.jwt_utils import TokenValidationError
from src.security.ws_auth import TOKEN_SUBPROTOCOL, verify_handshake_token

rounds_ws_router = APIRouter(prefix="/rounds")

# One process-wide manager: every Bene's room and its live connections live here,
# persisting each closed Round's outcome through the best-effort repo and publishing
# each shared lifecycle moment (Bene-scoped) to the Realtime Notifier — both IO seams
# are best-effort, so neither a DB nor a Notifier hiccup can break a live Round.
rooms = RoomManager(
    repo=OutcomesRepository(),
    notifier=NotificationProducer(NotifierClient()),
)


@rounds_ws_router.websocket("/ws/{poi_id}")
async def round_room(websocket: WebSocket, poi_id: int):
    """Join a connection to a Bene's room for the life of the connection.

    Refuses the handshake (1008) before joining any room if the JWT is missing or
    invalid, so an unauthorized client never sees a Bene's state."""
    offered = websocket.scope.get("subprotocols", [])
    try:
        payload = verify_handshake_token(
            websocket.query_params.get("access_token"), offered
        )
    except TokenValidationError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = str(payload["sub"])
    accepted = TOKEN_SUBPROTOCOL if TOKEN_SUBPROTOCOL in offered else None
    await websocket.accept(subprotocol=accepted)
    await rooms.connect(poi_id, websocket)
    try:
        while True:
            message = await websocket.receive_json()
            await rooms.handle(poi_id, websocket, user_id, message)
    except WebSocketDisconnect:
        rooms.disconnect(poi_id, websocket)
