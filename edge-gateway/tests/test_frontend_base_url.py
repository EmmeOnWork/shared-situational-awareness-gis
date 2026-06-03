"""Frontend base-URL wiring (slice 8, ADR-0002 Module 5).

The browser only ever talks to one origin — the gateway. That is realised by
pointing the Next frontend's ``NEXT_PUBLIC_BACKEND_URL`` at the gateway's
published front door rather than at the monolith backend directly, so both
framework calls (``/dashboards``, ``/auth``) and Widget calls (``/demographics``)
leave the browser as relative paths resolved against the single gateway origin.

Read as configuration (no Docker daemon), like the compose-stack contract tests:
we assert the stack is *wired* so the browser's base URL is the single front
door, not that a live browser made a request. The compose-parsing harness is
shared via conftest.
"""

import re

from conftest import (
    compose_doc,
    compose_env,
    compose_gateway,
    compose_service_built_from,
)


def _compose_default(value):
    """Resolve a ``${VAR:-default}`` interpolation to the default baked into the
    compose file — the value used when the environment supplies no per-env
    override. A bare ``${VAR}`` has no baked default; a plain string is itself."""
    if value is None:
        return None
    match = re.fullmatch(r"\$\{[^:}]+:-(.*)\}", str(value))
    if match:
        return match.group(1)
    if re.fullmatch(r"\$\{[^}]+\}", str(value)):
        return ""
    return str(value)


def _published_host_port(service):
    """The host-side port a service publishes — the origin a browser reaches."""
    for mapping in service.get("ports", []) or []:
        parts = str(mapping).split(":")  # "8080:8080" or "127.0.0.1:8080:8080"
        return parts[-2] if len(parts) >= 2 else parts[0]
    return None


def _url_port(url):
    """Port out of ``scheme://host:port/...`` (defaulting by scheme if absent)."""
    hostport = url.split("://", 1)[-1].split("/", 1)[0]
    if ":" in hostport:
        return hostport.rsplit(":", 1)[-1]
    return "443" if url.startswith("https://") else "80"


def test_frontend_base_url_points_at_the_gateway_single_origin():
    """ACCEPTANCE: the browser talks to one origin — the gateway. The Next
    frontend's ``NEXT_PUBLIC_BACKEND_URL`` resolves to the gateway's published
    front door (the host port the gateway publishes), NOT to the monolith backend,
    so every relative-path request the frontend makes lands on the single origin."""
    compose = compose_doc()
    _, gateway = compose_gateway(compose)
    _, frontend = compose_service_built_from(compose, "monastero-janus-frontend")
    backend_name, _ = compose_service_built_from(compose, "monastero-janus-backend")

    base_url = _compose_default(compose_env(frontend).get("NEXT_PUBLIC_BACKEND_URL"))
    assert base_url, "frontend must set NEXT_PUBLIC_BACKEND_URL (the gateway origin)"

    # It is the gateway's published origin: the host-side port the browser reaches.
    assert _url_port(base_url) == _published_host_port(gateway), (
        f"NEXT_PUBLIC_BACKEND_URL ({base_url}) must target the gateway's published "
        f"port ({_published_host_port(gateway)}) — the single front door"
    )

    # ...and explicitly NOT the monolith backend (the old second origin).
    assert backend_name not in base_url, (
        f"NEXT_PUBLIC_BACKEND_URL must point at the gateway, not the backend "
        f"({backend_name}); got {base_url}"
    )
