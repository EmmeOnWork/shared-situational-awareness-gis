"""Compose-orchestration contract (slice 6, ADR-0002 Module 3).

The top-level ``docker-compose.yml`` is the artifact under test. These tests read
the compose file as configuration (no Docker daemon needed) and assert the
invariants the slice promises: one command wires the four real components onto
one shared network, the gateway is the *only* published port, the upstreams are
injected as compose service names, and the gateway reuses the same
``edge-gateway/Caddyfile`` every other environment runs — no second copy of the
routing logic.

Reachability itself (a ``/demographics/ping`` 200 through the gateway) is the
documented manual smoke in the README — it needs the live stack; here we assert
the stack is *wired* to make that smoke pass.

The compose-parsing harness (``compose_doc`` and the component finders) lives in
conftest, shared with the other compose-contract slices.
"""

from conftest import (
    CADDYFILE,
    COMPOSE_FILE,
    compose_doc,
    compose_env,
    compose_gateway,
    compose_service_built_from,
    compose_services,
)


def _networks_of(service):
    networks = service.get("networks", [])
    if isinstance(networks, dict):
        return set(networks.keys())
    return set(networks)


def test_stack_brings_up_all_four_components_on_one_shared_network():
    """ACCEPTANCE: one top-level compose wires the four real components — the
    gateway, the demographic-service, the monolith backend, and the Next frontend
    — onto a single shared network, so one command stands up the whole stack with
    server-to-server reachability between them (G1/G2)."""
    compose = compose_doc()

    gateway_name, gateway = compose_gateway(compose)
    demographic_name, _ = compose_service_built_from(compose, "demographic-service")
    backend_name, _ = compose_service_built_from(compose, "monolith/backend")
    frontend_name, _ = compose_service_built_from(compose, "monolith/frontend")

    components = {gateway_name, demographic_name, backend_name, frontend_name}
    assert None not in components, (
        "expected gateway + demographic-service + monolith backend + frontend, "
        f"resolved {components}"
    )

    # All four sit on exactly one shared network — the seam that lets the gateway
    # reach every upstream server-to-server.
    networks_per_component = [
        _networks_of(compose_services(compose)[name]) for name in components
    ]
    shared = set.intersection(*networks_per_component)
    assert len(shared) == 1, (
        f"expected one shared network across all four components, got {networks_per_component}"
    )


def test_gateway_is_the_only_published_port():
    """The gateway is the single front door reachable from a browser/LAN: every
    OTHER published port must be loopback-only (127.0.0.1), for local DB/dev
    tooling (e.g. ju-postgres, for DBeaver/psql) rather than a second public
    entry point. Widget services and the monolith backend stay fully
    unpublished, reachable only server-to-server (ADR-0002)."""
    compose = compose_doc()
    gateway_name, _ = compose_gateway(compose)

    services = compose_services(compose)
    published = {name for name, service in services.items() if service.get("ports")}

    non_gateway_published = published - {gateway_name}
    for name in non_gateway_published:
        for port_mapping in services[name]["ports"]:
            assert str(port_mapping).startswith("127.0.0.1:"), (
                f"{name} publishes a non-loopback port ({port_mapping}); only the "
                f"gateway ({gateway_name}) may be reachable beyond localhost"
            )


def _upstream_host(url):
    """Pull the host out of an ``http://host:port`` upstream address."""
    return url.split("://", 1)[-1].split(":", 1)[0]


def test_gateway_upstreams_are_injected_as_compose_service_names():
    """The same Caddyfile meets real upstreams via injected configuration: each
    upstream the gateway env supplies is a *compose service name* on the shared
    network, not a hard-coded host. This is what closes G1 — the routing logic is
    reused unchanged and only the per-environment addresses differ."""
    compose = compose_doc()
    gateway_name, gateway = compose_gateway(compose)
    service_names = set(compose_services(compose))

    env = compose_env(gateway)
    demographic_name, _ = compose_service_built_from(compose, "demographic-service")
    characteristic_name, _ = compose_service_built_from(compose, "characteristic-service")
    backend_name, _ = compose_service_built_from(compose, "monolith/backend")
    frontend_name, _ = compose_service_built_from(compose, "monolith/frontend")

    # Each upstream the gateway interpolates points at the matching component's
    # compose service name — resolved server-to-server on the internal network.
    assert _upstream_host(env["DEMOGRAPHIC_UPSTREAM"]) == demographic_name
    assert _upstream_host(env["CHARACTERISTIC_UPSTREAM"]) == characteristic_name
    assert _upstream_host(env["MONOLITH_UPSTREAM"]) == backend_name
    assert _upstream_host(env["FRONTEND_UPSTREAM"]) == frontend_name

    # ...and every upstream host is genuinely a service in this compose (a real
    # internal name), never an external/hard-coded address.
    for var in (
        "DEMOGRAPHIC_UPSTREAM",
        "CHARACTERISTIC_UPSTREAM",
        "MONOLITH_UPSTREAM",
        "FRONTEND_UPSTREAM",
    ):
        assert _upstream_host(env[var]) in service_names


def test_gateway_reuses_the_existing_caddyfile_unchanged():
    """The gateway serves the SAME ``edge-gateway/Caddyfile`` the routing-contract
    tests run against — mounted, not copied — so the routing map lives in exactly
    one file (ADR-0002). It is mounted read-only, underscoring that the compose
    only injects configuration around the Caddyfile and never rewrites it."""
    compose = compose_doc()
    _, gateway = compose_gateway(compose)

    mounts = [v for v in gateway.get("volumes", []) if isinstance(v, str)]
    caddy_mounts = [m for m in mounts if m.split(":")[0].endswith("Caddyfile")]
    assert len(caddy_mounts) == 1, f"expected exactly one Caddyfile mount, got {caddy_mounts}"

    parts = caddy_mounts[0].split(":")
    source = parts[0]
    flags = parts[-1] if len(parts) > 2 else ""

    # It is the repo's real routing file (the contract tests' Caddyfile), present
    # on disk — not a second copy invented for compose.
    assert source == "./edge-gateway/Caddyfile"
    resolved = (COMPOSE_FILE.parent / source).resolve()
    assert resolved == CADDYFILE.resolve()
    assert "reverse_proxy /demographics" in CADDYFILE.read_text(encoding="utf-8")

    # Mounted read-only: the compose layers configuration around the Caddyfile,
    # it does not edit it.
    assert flags == "ro", f"Caddyfile should be mounted read-only, got flags {flags!r}"


def test_demographic_service_is_wired_for_the_reachability_smoke():
    """The reachability smoke (documented in the README) mints a ``demographics:read``
    token and calls ``/demographics/ping`` through the gateway, expecting 200 without
    seeding the database. For the service to verify that token, the compose injects
    its JWT-verification config — algorithm + verification key — so the smoke proves
    the demographic-service is reachable through the single origin (G2)."""
    compose = compose_doc()
    _, demographic = compose_service_built_from(compose, "demographic-service")

    env = compose_env(demographic)
    for key in ("JWT_ALGORITHM", "JWT_VERIFICATION_KEY"):
        assert key in env, f"demographic-service must define {key} for the smoke"
        assert str(env[key]).strip(), f"{key} must be a non-empty value"
