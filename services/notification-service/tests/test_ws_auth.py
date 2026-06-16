"""Unit: WS-handshake token extraction + verification (slice 3).

The deep, small module behind the WebSocket gate. It pulls a monolith JWT off a
handshake — from the ``?access_token=`` query param OR a ``["access_token",
<jwt>]`` subprotocol pair — and verifies it (reusing jwt_utils). A missing or
invalid token is rejected. No FastAPI/WebSocket here: the unit takes the raw
handshake pieces, so it is testable with a plain string + list.
"""

import pytest

from src.notifier.ws_auth import verify_handshake_token
from src.security.jwt_utils import TokenValidationError
from tests.conftest import make_token


def test_token_in_query_param_is_found_and_verified():
    """A valid JWT supplied as the access_token query param returns its payload."""
    payload = verify_handshake_token(make_token(), subprotocols=[])

    assert payload["sub"] == "1"


def test_token_in_subprotocol_pair_is_found_and_verified():
    """When no query param is present, a valid JWT carried as the value after the
    ``access_token`` subprotocol sentinel is found and verified."""
    token = make_token()

    payload = verify_handshake_token(None, subprotocols=["access_token", token])

    assert payload["sub"] == "1"


def test_missing_token_is_rejected():
    """No query param and no token-bearing subprotocol is refused outright — the
    handshake carried no credential to verify."""
    with pytest.raises(TokenValidationError):
        verify_handshake_token(None, subprotocols=[])


def test_invalid_token_is_rejected():
    """A present-but-bogus token fails verification and is refused."""
    with pytest.raises(TokenValidationError):
        verify_handshake_token("not-a-real-jwt", subprotocols=[])
