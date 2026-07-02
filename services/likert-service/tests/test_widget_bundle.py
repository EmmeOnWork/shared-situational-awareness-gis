import pytest

from src.app import WIDGET_BUNDLE

WIDGET_JS = "/likert/widget.js"


def test_widget_js_returns_503_with_build_hint_when_bundle_absent(client):
    """Until `make ui` builds the bundle, the route answers 503 with a hint —
    not a 404 or a stack trace — so an operator knows the UI step is pending
    (sibling-widget parity)."""
    resp = client.get(WIDGET_JS)

    assert resp.status_code == 503
    assert "make ui" in resp.json()["detail"]


def test_widget_js_is_unguarded(client):
    """The bundle is served **without** a JWT — a browser <script> load carries
    no token. Reaching the route with no Authorization header never yields a 401,
    proving no auth guard sits in front of the bundle; the data route stays
    guarded (see test_auth)."""
    resp = client.get(WIDGET_JS)

    assert resp.status_code != 401


@pytest.fixture
def built_bundle():
    """Materialise a tiny bundle where the route serves it, so a test can assert
    on the *served* file, then remove it to leave the tree clean."""
    WIDGET_BUNDLE.parent.mkdir(parents=True, exist_ok=True)
    WIDGET_BUNDLE.write_text("/* likert-widget test bundle */", encoding="utf-8")
    yield WIDGET_BUNDLE
    WIDGET_BUNDLE.unlink(missing_ok=True)


def test_widget_js_served_with_no_cache(client, built_bundle):
    """When the bundle is present it is served with ``Cache-Control: no-cache`` so
    a browser revalidates and can never serve a stale widget after a redeploy."""
    resp = client.get(WIDGET_JS)

    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-cache"
