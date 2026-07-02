def test_openapi_schema_lists_health(client):
    resp = client.get("/openapi.json")

    assert resp.status_code == 200
    assert "/health" in resp.json()["paths"]


def test_openapi_schema_lists_both_guarded_data_routes(client):
    """Both data routes are published in the schema; the bundle route is hidden via
    include_in_schema=False (the unguarded exception)."""
    paths = client.get("/openapi.json").json()["paths"]

    assert "/prezzari/locazione" in paths
    assert "/prezzari/lavori" in paths
    assert "/prezzari/widget.js" not in paths
