def test_cors_echoes_frontend_origin(client):
    origin = "https://dashboard.example.com"

    resp = client.get("/health", headers={"Origin": origin})

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == origin


def test_cors_preflight_allowed(client):
    origin = "https://dashboard.example.com"

    resp = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == origin
