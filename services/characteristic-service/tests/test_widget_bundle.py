BUNDLE = "/characteristic/widget.js"


def test_widget_bundle_is_unguarded(client):
    """The UI bundle is a plain <script> load and carries no bearer token, so it
    must NOT sit behind the auth guard. Reachable without a token: 200 when built,
    503 when not yet built in this test image — never 401/403."""
    resp = client.get(BUNDLE)

    assert resp.status_code != 401
    assert resp.status_code != 403
    assert resp.status_code in (200, 503)
