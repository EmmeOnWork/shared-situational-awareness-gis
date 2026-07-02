import jwt

from src.config import get_settings


class TokenValidationError(Exception):
    """Raised when a token cannot be verified or fails claim validation."""


def _normalize_multiline_key(key: str | None) -> str | None:
    """Allow PEM keys supplied via single-line env vars (``\\n`` escapes)."""
    if not key:
        return key
    return key.replace("\\n", "\n")


def verify_access_token(token: str) -> dict:
    """Verify a monolith-issued *access* token with the shared asymmetric key.

    Verify-only: this service never creates tokens. The algorithm is pinned to
    the configured one, so a token signed with a different algorithm fails.
    Mirrors the monolith's contract (copied, not imported — ADR-0001): a refresh
    token, a token missing the ``role`` claim, or one missing the ``scope`` claim
    is rejected. Any failure raises :class:`TokenValidationError`, which callers
    translate to HTTP 401.
    """
    settings = get_settings()
    algorithm = settings.jwt_algorithm
    key = _normalize_multiline_key(settings.jwt_verification_key)

    try:
        payload = jwt.decode(token, key, algorithms=[algorithm])
    except jwt.PyJWTError as exc:
        raise TokenValidationError("Invalid or expired JWT token") from exc

    if "role" not in payload:
        raise TokenValidationError("Token missing role claim")

    token_type = payload.get("token_type")
    if token_type is not None and token_type != "access":
        raise TokenValidationError("Token is not an access token")

    if not isinstance(payload.get("scope"), str):
        raise TokenValidationError("Token missing scope claim")

    return payload
