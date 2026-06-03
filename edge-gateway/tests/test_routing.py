import json

import httpx
import websocket  # the `websocket-client` package


def _ws_url(gateway_base, path):
    """Turn the gateway's http base URL into a ws:// URL for the given path."""
    return gateway_base.replace("http://", "ws://", 1) + path


def test_echo_upstream_answers_with_its_own_identity(echo_upstream):
    """The harness's stub upstream is trustworthy on its own: hit it directly and
    it names itself, so a later routing assertion that reads this name is really
    proving the gateway picked this upstream."""
    upstream = echo_upstream("demographic-service")

    resp = httpx.get(f"{upstream.address}/anything")

    assert resp.json()["upstream"] == "demographic-service"


def test_ws_echo_upstream_accepts_upgrade_and_names_itself(ws_echo_upstream):
    """The harness's WebSocket stub is trustworthy on its own: connect to it
    directly, the upgrade completes, it greets with its identity, and it echoes —
    so a later routing assertion that reads this identity is really proving the
    gateway carried the upgrade through to this upstream."""
    upstream = ws_echo_upstream("realtime-upstream")

    conn = websocket.create_connection(_ws_url(upstream.address, "/anything"), timeout=10)
    try:
        greeting = json.loads(conn.recv())
        conn.send("ping")
        echo = conn.recv()
    finally:
        conn.close()

    assert greeting["upstream"] == "realtime-upstream"
    assert echo == "ping"


def test_demographics_prefix_routes_to_demographic_upstream(echo_upstream, gateway):
    """ACCEPTANCE: the tracer slice. A real request for the /demographics prefix,
    sent to the live gateway, is answered by the demographic-service upstream."""
    demographic = echo_upstream("demographic-service")
    gw = gateway({"DEMOGRAPHIC_UPSTREAM": demographic.address})

    resp = httpx.get(f"{gw}/demographics/raw?territory=Milano")

    assert resp.json()["upstream"] == "demographic-service"


def test_demographic_upstream_address_comes_from_env_not_hardcoded(
    echo_upstream, gateway
):
    """The same Caddyfile must follow whatever DEMOGRAPHIC_UPSTREAM is injected,
    proving the upstream address is env-substituted rather than baked in. We point
    the gateway at a stub with a distinct identity and require that exact one to
    answer — a hard-coded address could not."""
    injected = echo_upstream("demographic-via-injected-env")
    gw = gateway({"DEMOGRAPHIC_UPSTREAM": injected.address})

    resp = httpx.get(f"{gw}/demographics/raw")

    assert resp.json()["upstream"] == "demographic-via-injected-env"


def test_websocket_upgrade_passes_through_gateway(ws_echo_upstream, gateway):
    """ACCEPTANCE: the gateway carries a WebSocket upgrade end-to-end. A real WS
    handshake sent to the live gateway reaches an upstream that accepts the
    upgrade, and a frame round-trips back — proving a live bidirectional tunnel,
    not a 101 that dies.

    Caddy's reverse_proxy carries upgrades on *any* proxied route, so the future
    realtime Widgets rely on exactly this capability and nothing more; we prove
    it through the one route that exists today (/demographics) by pointing its
    upstream at a WebSocket stub."""
    realtime = ws_echo_upstream("realtime-upstream")
    gw = gateway({"DEMOGRAPHIC_UPSTREAM": realtime.address})

    conn = websocket.create_connection(_ws_url(gw, "/demographics/realtime"), timeout=10)
    try:
        greeting = json.loads(conn.recv())
        conn.send("ping")
        echo = conn.recv()
    finally:
        conn.close()

    assert greeting["upstream"] == "realtime-upstream"
    assert echo == "ping"
