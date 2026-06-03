"""Routing contract for slice 2: the monolith catch-all and the frontend root.

These complete the routing map's default behaviour — explicit widget prefixes
first (slice 1), the Next frontend at /, and the monolith backend as the final
catch-all. Like the rest of the suite they treat the gateway as a black box:
stand up an echo upstream, launch the real Caddy in front of it, and assert
*which upstream answered* — never Caddy internals. Each test wires only the
upstream it asserts on; the others default to an inert address (see the
``gateway`` fixture), so a misroute surfaces as a loud 502 rather than a false
pass.
"""

import httpx


def test_unknown_prefix_routes_to_monolith_catch_all(echo_upstream, gateway):
    """ACCEPTANCE: the catch-all default never silently breaks. A path the gateway
    has no explicit route for (an unknown prefix like /dashboards) is answered by
    the monolith backend — the seam that lets the monolith add routes with zero
    gateway changes."""
    monolith = echo_upstream("monolith-backend")
    gw = gateway({"MONOLITH_UPSTREAM": monolith.address})

    resp = httpx.get(f"{gw}/dashboards/overview")

    assert resp.json()["upstream"] == "monolith-backend"


def test_root_routes_to_frontend(echo_upstream, gateway):
    """ACCEPTANCE: the gateway serves the Next frontend at /. A request for the
    site root reaches the frontend upstream — not the monolith catch-all — so the
    browser talks to a single origin that hands back the app shell."""
    frontend = echo_upstream("frontend")
    gw = gateway({"FRONTEND_UPSTREAM": frontend.address})

    resp = httpx.get(f"{gw}/")

    assert resp.json()["upstream"] == "frontend"
