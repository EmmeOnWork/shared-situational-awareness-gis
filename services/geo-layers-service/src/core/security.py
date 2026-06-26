"""Auth: verify the monolith's HS256 access token (this service issues none).

Auth-only by design: any logged-in monolith user may read the public map layers,
so NO extra scope is required — nothing to grant in the monolith (keeps the
monolith untouched). Mirrors the monolith's verify contract (copied, not imported
— ADR-0001): reject a token missing the ``role`` claim.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.core.settings import get_settings

# auto_error=False so we send our own 401 with a WWW-Authenticate header.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

_UNAUTH = {"WWW-Authenticate": "Bearer"}


def require_auth(token: str | None = Depends(oauth2_scheme)) -> dict:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Bearer token", _UNAUTH)
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_verification_key,
            algorithms=[get_settings().jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", _UNAUTH
        ) from exc
    if "role" not in payload:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token missing role claim", _UNAUTH
        )
    return payload
