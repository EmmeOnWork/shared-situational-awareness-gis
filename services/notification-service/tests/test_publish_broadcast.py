"""Acceptance: the realtime pipe delivers end-to-end (slice 2).

A single server-side `POST /notifications/publish` must fan a self-describing
Notification out to every connected WebSocket client. This exercises the whole
slice through its public surfaces — the WS endpoint clients subscribe to and the
publish ingress — with no knowledge of the Hub's internals. The token on the WS
query string is accepted but NOT verified here (that is slice 3).

Toast *rendering* (colour by severity, auto-dismiss) is host-coupled glue and is
verified manually per the task's acceptance criteria; this asserts the wire
delivery the toast is built on.

Since slice 3 the WS handshake verifies the JWT, so the subscribing client mints
a valid token; this still exercises only the publish→broadcast→deliver wire.
"""

from tests.conftest import make_token

PUBLISH_URL = "/notifications/publish"

VALID = {"severity": "warning", "title": "Round chiuso", "body": "Tutti hanno votato"}


def test_publish_reaches_connected_websocket_client(client):
    """Connect a client, publish once, and the client receives exactly that
    Notification (severity + text), proving the publish→broadcast→deliver pipe."""
    with client.websocket_connect(
        f"/notifications/ws?access_token={make_token()}"
    ) as ws:
        resp = client.post(PUBLISH_URL, json=VALID)
        assert resp.status_code == 200

        received = ws.receive_json()

    assert received["severity"] == "warning"
    assert received["title"] == "Round chiuso"
    assert received["body"] == "Tutti hanno votato"


def test_publish_rejects_unknown_severity_at_the_ingress(client):
    """An invalid Notification (severity outside info/warning/success) is rejected
    by the ingress with a validation error, never broadcast."""
    resp = client.post(PUBLISH_URL, json={**VALID, "severity": "critical"})

    assert resp.status_code == 422


def test_publish_rejects_half_specified_scope_at_the_ingress(client):
    """A scope missing `value` (or `axis`) is rejected by the ingress, never
    broadcast as if it were global."""
    resp = client.post(PUBLISH_URL, json={**VALID, "scope": {"axis": "workshop"}})

    assert resp.status_code == 422
