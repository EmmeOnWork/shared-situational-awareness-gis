from dataclasses import dataclass

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

from src.security.jwt_utils import TokenValidationError, verify_access_token


@dataclass
class AuthenticatedUser:
    user_id: int
    email: str
    role: str
    scopes: list[str]


# auto_error=False so we can craft our own 401 with a WWW-Authenticate header.
# tokenUrl is cosmetic (Swagger metadata only) — this service has no login route.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    scopes={},
    auto_error=False,
)


def _extract_scopes(payload: dict) -> list[str]:
    raw_scope = payload.get("scope")
    if isinstance(raw_scope, str):
        return [scope for scope in raw_scope.split(" ") if scope]

    raise TokenValidationError("Token missing scope claim")


def _build_authenticate_header(security_scopes: SecurityScopes) -> str:
    if security_scopes.scopes:
        return f'Bearer scope="{security_scopes.scope_str}"'
    return "Bearer"


def get_current_user(
    security_scopes: SecurityScopes,
    token: str | None = Depends(oauth2_scheme),
) -> AuthenticatedUser:
    authenticate_value = _build_authenticate_header(security_scopes)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": authenticate_value},
        )

    try:
        payload = verify_access_token(token)
    except TokenValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": authenticate_value},
        ) from exc

    try:
        user_id = int(payload["sub"])
        email = str(payload["email"])
        role = str(payload["role"])
        scopes = _extract_scopes(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": authenticate_value},
        ) from exc

    missing_scopes = [
        required_scope
        for required_scope in security_scopes.scopes
        if required_scope not in scopes
    ]
    if missing_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": authenticate_value},
        )

    return AuthenticatedUser(user_id=user_id, email=email, role=role, scopes=scopes)


def require_scopes(required_scopes: list[str]):
    def _scopes_dependency(
        current_user: AuthenticatedUser = Security(
            get_current_user,
            scopes=required_scopes,
        ),
    ) -> AuthenticatedUser:
        return current_user

    return _scopes_dependency
