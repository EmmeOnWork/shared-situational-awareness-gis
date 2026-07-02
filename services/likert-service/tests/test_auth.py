"""The copied JWT verify guards the single data route.

The Scala Likert's data route is authentication-only: a valid monolith-issued JWT
is required, but no particular scope — it is not a sensitive (Bene) widget. The
unguarded bundle (see test_widget_bundle) is deliberately the opposite.
"""

from unittest.mock import patch

from src.routers.likert.comune_resolver import Comune

GRADIMENTO = "/likert/gradimento?lat=40.9&lng=15.2&vocazione=dimora-del-benessere"


def test_data_route_requires_a_token(client):
    """No Authorization header ⇒ 401: the data route sits behind the guard."""
    resp = client.get(GRADIMENTO)

    assert resp.status_code == 401


def test_data_route_passes_with_a_valid_token(client, auth_header):
    """A valid access token (no scope needed) is admitted — proving the guard
    verifies the monolith JWT and the route gates on authentication alone. The
    comune resolution and competitor join are mocked so this stays an auth check,
    not a DB call."""
    with patch(
        "src.routers.likert.likert_router.resolve_comune",
        return_value=Comune(region_id=42, name="Sant'Angelo dei Lombardi"),
    ), patch(
        "src.routers.likert.likert_router.find_competitors",
        return_value=[],
    ):
        resp = client.get(GRADIMENTO, headers=auth_header())

    assert resp.status_code == 200


def test_data_route_rejects_a_token_missing_the_role_claim(client, auth_header):
    """The copied verifier mirrors the monolith contract: a token without the
    ``role`` claim is rejected, so the guard is the real verify, not a stub."""
    resp = client.get(GRADIMENTO, headers=auth_header(include_role=False))

    assert resp.status_code == 401
