WIDGET_JS = "/reuse/widget.js"


def test_widget_js_returns_503_with_build_hint_when_bundle_absent(client):
    """Until `make ui` builds the bundle, the route answers 503 with a hint —
    not a 404 or a stack trace — so an operator knows the UI step is pending
    (demographic parity)."""
    resp = client.get(WIDGET_JS)

    assert resp.status_code == 503
    assert "make ui" in resp.json()["detail"]


def test_widget_js_is_unguarded(client):
    """The bundle is served **without** a JWT — a browser <script> load carries
    no token. Reaching the 503 (build-hint) branch with no Authorization header
    proves no auth guard sits in front of the bundle route; data routes stay
    guarded (see test_benes_router)."""
    resp = client.get(WIDGET_JS)

    assert resp.status_code != 401
