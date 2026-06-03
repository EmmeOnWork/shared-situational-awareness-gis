"""Auth pass-through contract (task 03).

The gateway forwards the monolith-issued ``Authorization: Bearer`` token to the
upstream untouched and verifies nothing itself — each widget service keeps
checking the JWT exactly as it does today (ADR-0002). These tests treat the
gateway as a black box: they send a request to the live gateway and assert what
the upstream *received*, never inspecting Caddy internals.
"""

import httpx


def test_echo_upstream_reports_received_headers(echo_upstream):
    """The stub is trustworthy about what it received: hit it directly with a
    header and it reports that header back (lower-cased name, value verbatim). A
    later hop assertion that reads ``received_headers`` is then really proving
    what arrived at the upstream — mirrors the identity self-test in test_routing."""
    upstream = echo_upstream("demographic-service")

    resp = httpx.get(f"{upstream.address}/anything", headers={"X-Probe": "hello"})

    assert resp.json()["received_headers"]["x-probe"] == "hello"


def test_authorization_bearer_survives_proxy_hop(echo_upstream, gateway):
    """ACCEPTANCE: a monolith-issued Bearer token reaches the upstream byte-for-byte
    unchanged. The gateway is pass-through, not a checkpoint, so the token the
    service verifies is exactly the one the client sent."""
    demographic = echo_upstream("demographic-service")
    gw = gateway({"DEMOGRAPHIC_UPSTREAM": demographic.address})
    # Stands in for the opaque monolith-issued JWT; only that it survives the hop
    # verbatim matters, not its contents (kept low-entropy so secret scanners
    # don't flag the fixture).
    token = "monolith-issued.jwt.fixture-not-a-secret"

    resp = httpx.get(
        f"{gw}/demographics/raw",
        headers={"Authorization": f"Bearer {token}"},
    )

    received = resp.json()["received_headers"]
    assert received["authorization"] == f"Bearer {token}"


def test_gateway_forwards_token_it_does_not_verify(echo_upstream, gateway):
    """Criterion #2: the gateway verifies nothing of its own. A token it could
    never validate still reaches the upstream with 200 and arrives unchanged —
    proof the gateway gatekeeps nothing. A gateway that verified would 401 before
    the upstream ever saw the request; verification stays the service's job."""
    demographic = echo_upstream("demographic-service")
    gw = gateway({"DEMOGRAPHIC_UPSTREAM": demographic.address})
    unverifiable = "Bearer not-a-real-jwt.deadbeef"

    resp = httpx.get(f"{gw}/demographics/raw", headers={"Authorization": unverifiable})

    body = resp.json()
    assert resp.status_code == 200
    assert body["upstream"] == "demographic-service"
    assert body["received_headers"]["authorization"] == unverifiable
