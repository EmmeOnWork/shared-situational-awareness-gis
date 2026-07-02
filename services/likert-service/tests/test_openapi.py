def test_openapi_schema_lists_health(client):
    resp = client.get("/openapi.json")

    assert resp.status_code == 200
    assert "/health" in resp.json()["paths"]


def test_openapi_schema_lists_the_guarded_data_route(client):
    """The single data route is published in the schema (the bundle route is
    hidden via include_in_schema=False, the unguarded exception)."""
    resp = client.get("/openapi.json")

    assert "/likert/gradimento" in resp.json()["paths"]
