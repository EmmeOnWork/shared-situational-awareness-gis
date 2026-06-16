"""WS-handshake authentication: pull the monolith JWT off the handshake and verify.

The browser cannot set an ``Authorization`` header on a WebSocket handshake, so the
token rides one of two ways: the ``?access_token=`` query param, or a subprotocol
sentinel pair ``["access_token", <jwt>]`` (the value after the ``access_token``
sentinel). Verification reuses ``jwt_utils`` (ADR-0002) — the same check the sibling
services apply, not Supabase RLS. A missing or invalid token raises
``TokenValidationError`` so the endpoint can refuse the connection before
registering it with the Hub.
"""

from src.security.jwt_utils import TokenValidationError, verify_access_token

# The subprotocol that flags the next protocol value as the bearer token, mirroring
# the k8s apiserver convention. The element after it on the handshake is the JWT.
TOKEN_SUBPROTOCOL = "access_token"


def _extract_token(access_token: str | None, subprotocols: list[str]) -> str | None:
    """Locate the token on a handshake: query param wins, else the subprotocol pair."""
    if access_token:
        return access_token
    if TOKEN_SUBPROTOCOL in subprotocols:
        sentinel = subprotocols.index(TOKEN_SUBPROTOCOL)
        if sentinel + 1 < len(subprotocols):
            return subprotocols[sentinel + 1]
    return None


def verify_handshake_token(access_token: str | None, subprotocols: list[str]) -> dict:
    """Return the verified JWT payload for a handshake, or raise.

    Raises ``TokenValidationError`` when no token is present or it does not verify.
    """
    token = _extract_token(access_token, subprotocols)
    if not token:
        raise TokenValidationError("Missing WebSocket handshake token")
    return verify_access_token(token)
