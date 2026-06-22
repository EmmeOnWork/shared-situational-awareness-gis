"""The copied JWT verify guards the (placeholder) data routes.

v1 is authentication-only: a valid monolith-issued JWT is required, but no
particular scope — a dedicated ``rounds:*`` scope is out of scope for this PRD.
This is the seam a participation scope slots into later without touching routes.
"""

PING = "/rounds/ping"


def test_data_route_requires_a_token(client):
    """No Authorization header ⇒ 401: the data route sits behind the guard, unlike
    the unguarded bundle (see test_widget_bundle)."""
    resp = client.get(PING)

    assert resp.status_code == 401


def test_data_route_passes_with_a_valid_token(client, auth_header):
    """A valid access token (no scope needed) is admitted — proving the guard
    verifies the monolith JWT and v1 gates on authentication alone."""
    resp = client.get(PING, headers=auth_header())

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_data_route_rejects_a_token_missing_the_role_claim(client, auth_header):
    """The copied verifier mirrors the monolith contract: a token without the
    ``role`` claim is rejected, so the guard is the real verify, not a stub."""
    resp = client.get(PING, headers=auth_header(include_role=False))

    assert resp.status_code == 401
