"""One-line widget registration proven (task 05).

The seam's core promise: onboarding a new Widget service is a one-line,
reversible change to the single route table — claim a fresh top-level prefix and
it routes to its own upstream, winning over the monolith catch-all. Like the
rest of the suite this is a black-box routing assertion: stand up echo stubs,
launch the real Caddy in front of them, and read *which upstream answered* —
never Caddy internals.
"""

import httpx


def test_freshly_registered_prefix_wins_over_monolith_catch_all(echo_upstream, gateway):
    """ACCEPTANCE: registering a fresh top-level prefix (the canonical
    ``/geo-layers`` new-widget example) routes it to its own upstream and beats
    the monolith catch-all. Both upstreams run with distinct identities; a
    request for the new prefix is answered by the geo-layers service, not the
    monolith — proving the explicit prefix is matched before the matcher-less
    catch-all. Without the route, this path would fall through to the monolith,
    so the single assertion proves both 'reaches its own upstream' and 'beats
    the catch-all'."""
    geo_layers = echo_upstream("geo-layers-service")
    monolith = echo_upstream("monolith-backend")
    gw = gateway(
        {
            "GEO_LAYERS_UPSTREAM": geo_layers.address,
            "MONOLITH_UPSTREAM": monolith.address,
        }
    )

    resp = httpx.get(f"{gw}/geo-layers/styles?territory=Milano")

    assert resp.json()["upstream"] == "geo-layers-service"
