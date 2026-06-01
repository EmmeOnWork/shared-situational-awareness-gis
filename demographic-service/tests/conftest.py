import os
import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# --- Test JWT setup -------------------------------------------------------
# Generate an RSA keypair for the session and point the service's verifier at
# the public half BEFORE importing the app, so verification is hermetic and
# mimics "monolith-issued" tokens (asymmetric verify-only).
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
_PUBLIC_PEM = (
    _private_key.public_key()
    .public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)

os.environ["JWT_ALGORITHM"] = "RS256"
os.environ["JWT_VERIFICATION_KEY"] = _PUBLIC_PEM

from fastapi.testclient import TestClient  # noqa: E402

from src.app import app  # noqa: E402


def make_token(
    *,
    scope="demographics:read",
    include_scope=True,
    include_role=True,
    token_type="access",
    algorithm="RS256",
    key=None,
    **overrides,
):
    """Mint a signed token for tests. Defaults to a valid access token carrying
    the demographics:read scope; kwargs let each test bend exactly one thing.

    Claim names match what the monolith issues (``token_type``, ``scope`` as a
    space-delimited string)."""
    payload = {
        "sub": "1",
        "email": "test@example.com",
        "token_type": token_type,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    if include_role:
        payload["role"] = "VIEWER"
    if include_scope:
        payload["scope"] = scope
    payload.update(overrides)
    signing_key = key if key is not None else _PRIVATE_PEM
    return pyjwt.encode(payload, signing_key, algorithm=algorithm)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_header():
    def _header(**kwargs):
        return {"Authorization": f"Bearer {make_token(**kwargs)}"}

    return _header
