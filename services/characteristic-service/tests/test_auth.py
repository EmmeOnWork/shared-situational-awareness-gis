from tests.conftest import make_token

PROTECTED = "/characteristic/ping"


def test_valid_token_allows_access(client, auth_header):
    resp = client.get(PROTECTED, headers=auth_header())

    assert resp.status_code == 200


def test_missing_token_is_unauthorized(client):
    resp = client.get(PROTECTED)

    assert resp.status_code == 401


def test_token_with_any_scope_is_allowed(client, auth_header):
    """v1 is authentication-only: the guard is ``require_scopes([])``, so a valid
    JWT carrying an unrelated scope still passes — there is **no** 403. This locks
    the deferred-roles decision; the Workshop Master gate is the future seam."""
    resp = client.get(PROTECTED, headers=auth_header(scope="weather:read"))

    assert resp.status_code == 200


def test_tampered_token_is_unauthorized(client):
    token = make_token()
    header, body, signature = token.split(".")
    tampered = f"{header}.{body}.{signature[:-4]}AAAA"

    resp = client.get(PROTECTED, headers={"Authorization": f"Bearer {tampered}"})

    assert resp.status_code == 401


def test_wrong_algorithm_token_is_unauthorized(client):
    # Signed with HS256 instead of the pinned RS256 → rejected.
    token = make_token(algorithm="HS256", key="symmetric-secret")

    resp = client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


def test_missing_role_claim_is_unauthorized(client):
    token = make_token(include_role=False)

    resp = client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


def test_missing_scope_claim_is_unauthorized(client):
    token = make_token(include_scope=False)

    resp = client.get(PROTECTED, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


def test_service_issues_no_tokens(client):
    """Verify-only: there must be no login / signup / refresh / token routes."""
    paths = client.get("/openapi.json").json()["paths"]

    issuance = {"login", "signup", "refresh", "token"}
    assert not any(any(word in path for word in issuance) for path in paths)
