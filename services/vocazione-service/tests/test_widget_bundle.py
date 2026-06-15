"""The unguarded bundle route — reuse/characteristic-service parity.

This Widget has NO data endpoint, so the bundle route is the service's whole
public HTTP surface beyond /health. It must serve the built bundle to a bare
browser <script> load (no token), answer 503 with a build hint until the bundle
is built, and carry Cache-Control: no-cache so a redeploy can never be masked by
a stale cached bundle.
"""

import src.app as app_module

WIDGET_JS = "/vocazione/widget.js"


def test_widget_js_returns_503_with_build_hint_when_bundle_absent(client):
    """Until `make ui` builds the bundle, the route answers 503 with a hint —
    not a 404 or a stack trace — so an operator knows the UI step is pending
    (reuse-service parity)."""
    resp = client.get(WIDGET_JS)

    assert resp.status_code == 503
    assert "make ui" in resp.json()["detail"]


def test_widget_js_is_unguarded(client):
    """The bundle is served **without** a JWT — a browser <script> load carries
    no token. Reaching the 503 (build-hint) branch with no Authorization header
    proves no auth guard sits in front of the route. This Widget has no data
    route at all, so nothing here is ever guarded."""
    resp = client.get(WIDGET_JS)

    assert resp.status_code != 401


def test_widget_js_serves_js_with_no_cache_when_built(client, tmp_path, monkeypatch):
    """When the bundle exists the route serves it as JavaScript with
    Cache-Control: no-cache, so browsers revalidate and never hold a stale
    bundle after a redeploy."""
    bundle = tmp_path / "vocazione-widget.js"
    bundle.write_text("// built bundle", encoding="utf-8")
    monkeypatch.setattr(app_module, "WIDGET_BUNDLE", bundle)

    resp = client.get(WIDGET_JS)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/javascript")
    assert resp.headers["cache-control"] == "no-cache"
