"""The UI half of the full-stack Widget: the bundle is served, and unguarded.

A browser ``<script>`` load carries no bearer token, so the bundle route MUST NOT
require auth (unlike the data routes). The bundle file itself is a build artifact
(git-ignored), so we assert the *contract* — served and open — not its bytes.
"""


def test_widget_bundle_is_unguarded(client):
    """GET /demographics/widget.js never returns 401 — the code is public."""
    res = client.get("/demographics/widget.js")
    # 200 when built locally, 503 when the bundle has not been built; never 401.
    assert res.status_code in (200, 503)
    assert res.status_code != 401


def test_widget_bundle_served_as_javascript_when_built(client):
    """When the bundle exists it is served with a JS content type."""
    res = client.get("/demographics/widget.js")
    if res.status_code == 200:
        assert "javascript" in res.headers["content-type"]
    else:
        # Not built in this environment: the route says so explicitly.
        assert res.status_code == 503
        assert "not built" in res.json()["detail"].lower()
