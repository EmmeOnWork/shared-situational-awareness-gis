"""Routing-contract test harness for the edge gateway.

The gateway is treated as a black box: tests stand up tiny echo upstreams (each
answers with its own identity), launch the real Caddy binary in front of them,
then send HTTP requests to the gateway and assert *which upstream answered*.
Nothing here inspects Caddy internals, so the route table can be rewritten — or
the proxy swapped — without touching the tests.
"""

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

CADDYFILE = Path(__file__).resolve().parent.parent / "Caddyfile"
# tests -> edge-gateway -> repo root, where the single top-level compose lives.
COMPOSE_FILE = CADDYFILE.parent.parent / "docker-compose.yml"


def _load_dotenv():
    """Load ``KEY=VALUE`` lines from ``edge-gateway/.env`` into the environment,
    never overriding a value already set (an explicit export or CI value wins).
    Lets a developer record ``CADDY_BIN`` once in an untracked ``.env`` instead of
    exporting it every run. Zero-dependency on purpose — keeps the dev deps
    minimal and the .env optional: absent, the harness still skips cleanly."""
    env_file = CADDYFILE.parent / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


# --- Compose-contract helpers --------------------------------------------------
# The top-level docker-compose.yml read as plain configuration (no Docker daemon).
# Shared by every compose-contract slice so each identifies a component by what it
# is built from / mounts — never by a name a refactor could rename.


def compose_doc():
    """Parse the top-level compose file as plain configuration."""
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def compose_services(compose):
    return compose.get("services", {})


def compose_service_built_from(compose, context_suffix):
    """``(name, definition)`` of the service whose build context ends with
    ``context_suffix`` (e.g. ``demographic-service``) — a component identified by
    the repo it is built from, not by a name a refactor could rename."""
    for name, service in compose_services(compose).items():
        build = service.get("build")
        context = build.get("context") if isinstance(build, dict) else build
        if context and str(context).rstrip("/").endswith(context_suffix):
            return name, service
    return None, None


def compose_gateway(compose):
    """``(name, definition)`` of the gateway: the one service that mounts the
    edge-gateway Caddyfile (identified by that mount, not by a name)."""
    for name, service in compose_services(compose).items():
        for volume in service.get("volumes", []) or []:
            source = volume.split(":")[0] if isinstance(volume, str) else ""
            if source.endswith("edge-gateway/Caddyfile"):
                return name, service
    return None, None


def compose_env(service):
    """A service's ``environment`` as a dict, accepting both compose forms: the
    map form (``KEY: value``) and the list form (``- KEY=value`` / ``- KEY``)."""
    environment = service.get("environment", {})
    if isinstance(environment, dict):
        return {str(k): v for k, v in environment.items()}
    result = {}
    for entry in environment:
        key, _, value = str(entry).partition("=")
        result[key] = value if "=" in entry else None
    return result


@dataclass
class Upstream:
    """A running echo stub: its base address and the identity it answers with."""

    name: str
    address: str


def _make_echo_handler(name):
    class EchoHandler(BaseHTTPRequestHandler):
        def _respond(self):
            # Report what arrived so a test can assert what survived the hop.
            # Header names are case-insensitive (RFC 7230) and proxies canonicalise
            # them, so we lower-case the keys; values are reported verbatim.
            received = {key.lower(): value for key, value in self.headers.items()}
            body = json.dumps(
                {"upstream": name, "received_headers": received}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # Any path, any common method, answers with this stub's identity.
        do_GET = _respond
        do_POST = _respond

        def log_message(self, *args):  # silence per-request stderr logging
            pass

    return EchoHandler


@pytest.fixture
def echo_upstream():
    """Factory: ``echo_upstream(name)`` starts a stub that answers every request
    with ``{"upstream": name}`` and returns its :class:`Upstream`. All stubs are
    torn down at the end of the test."""
    servers = []

    def _start(name):
        server = HTTPServer(("127.0.0.1", 0), _make_echo_handler(name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        port = server.server_address[1]
        return Upstream(name=name, address=f"http://127.0.0.1:{port}")

    yield _start

    for server, thread in servers:
        server.shutdown()
        thread.join(timeout=5)


# --- WebSocket echo stub -------------------------------------------------------
# A minimal, dependency-free WebSocket upstream: it accepts the upgrade, greets
# with its identity (so a routing assertion can read which upstream answered),
# then echoes frames. Just enough server-side WebSocket to prove the gateway
# carries an upgrade end-to-end — Caddy does the carrying; this only has to be a
# credible upstream that accepts one.

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # RFC 6455 handshake constant


def _ws_accept_key(client_key):
    digest = hashlib.sha1((client_key + _WS_GUID).encode()).digest()
    return base64.b64encode(digest).decode()


def _ws_send_text(wfile, text):
    """Write one unmasked text frame (server→client per RFC 6455)."""
    payload = text.encode()
    header = bytearray([0x81])  # FIN + text opcode
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack(">H", length)
    else:
        header.append(127)
        header += struct.pack(">Q", length)
    wfile.write(bytes(header) + payload)
    wfile.flush()


def _ws_recv_text(rfile):
    """Read one masked client frame; return its text, or None on close/EOF."""
    head = rfile.read(2)
    if len(head) < 2:
        return None
    opcode = head[0] & 0x0F
    masked = head[1] & 0x80
    length = head[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", rfile.read(2))[0]
    elif length == 127:
        length = struct.unpack(">Q", rfile.read(8))[0]
    mask = rfile.read(4) if masked else b"\x00\x00\x00\x00"
    data = bytearray(rfile.read(length))
    for i in range(length):
        data[i] ^= mask[i % 4]
    if opcode == 0x8:  # close
        return None
    return data.decode()


def _make_ws_echo_handler(name):
    class WSEchoHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"  # 101 Switching Protocols needs HTTP/1.1

        def do_GET(self):
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:  # not an upgrade — be a plain identity stub too
                body = json.dumps({"upstream": name}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(101)
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", _ws_accept_key(key))
            self.end_headers()
            self.close_connection = True  # the socket is now a WebSocket tunnel

            _ws_send_text(self.wfile, json.dumps({"upstream": name}))
            while True:
                message = _ws_recv_text(self.rfile)
                if message is None:
                    break
                _ws_send_text(self.wfile, message)

        def log_message(self, *args):  # silence per-request stderr logging
            pass

    return WSEchoHandler


@pytest.fixture
def ws_echo_upstream():
    """Factory: ``ws_echo_upstream(name)`` starts a stub that accepts a WebSocket
    upgrade, greets with ``{"upstream": name}``, then echoes every frame back, and
    returns its :class:`Upstream`. All stubs are torn down at the end of the test.
    Threaded so a connection parked in the echo loop never blocks teardown."""
    servers = []

    def _start(name):
        server = ThreadingHTTPServer(("127.0.0.1", 0), _make_ws_echo_handler(name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        port = server.server_address[1]
        return Upstream(name=name, address=f"http://127.0.0.1:{port}")

    yield _start

    for server, thread in servers:
        server.shutdown()
        thread.join(timeout=5)


def _caddy_binary():
    """Locate the Caddy binary via CADDY_BIN or PATH; skip if neither resolves,
    so the suite is green-when-present and clearly-skipped-when-absent rather
    than erroring deep in process launch."""
    candidate = os.environ.get("CADDY_BIN") or shutil.which("caddy")
    if not candidate or not Path(candidate).exists():
        pytest.skip(
            "caddy binary not found (set CADDY_BIN or put 'caddy' on PATH)"
        )
    return candidate


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_listening(port, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.05)
    return False


# The route table interpolates one upstream per route; a test usually asserts on
# a single route. Default every upstream to an inert, never-dialled address so
# Caddy still starts when a test wires only the upstream(s) it cares about. A test
# that exercises a route passes its own real upstream, which overrides the default
# here — the inert address is only ever reached if a test misroutes, where a 502
# is the loud failure we want.
_INERT_UPSTREAM = "http://127.0.0.1:9"  # discard port; nothing listens here
_DEFAULT_UPSTREAMS = {
    "FRONTEND_UPSTREAM": _INERT_UPSTREAM,
    "DEMOGRAPHIC_UPSTREAM": _INERT_UPSTREAM,
    "CHARACTERISTIC_UPSTREAM": _INERT_UPSTREAM,
    "GEO_LAYERS_UPSTREAM": _INERT_UPSTREAM,
    "MONOLITH_UPSTREAM": _INERT_UPSTREAM,
}


@pytest.fixture
def gateway():
    """Factory: ``gateway(upstreams)`` launches the real Caddy binary in front of
    the given upstreams and returns the gateway's base URL.

    ``upstreams`` maps the env-var names the Caddyfile interpolates to upstream
    addresses (e.g. ``{"DEMOGRAPHIC_UPSTREAM": "http://127.0.0.1:5001"}``). Any
    upstream a test omits defaults to an inert address (see ``_DEFAULT_UPSTREAMS``)
    so the full route table still starts. A free port is chosen and injected as the
    gateway's site address (``GATEWAY_SITE_ADDRESS=:<port>``) — the port-only form
    is plain HTTP, the same TLS-off posture every local run uses. The process is
    terminated at the end of the test.
    """
    caddy = _caddy_binary()
    processes = []

    def _start(upstreams):
        port = _free_port()
        env = {
            **os.environ,
            "GATEWAY_SITE_ADDRESS": f":{port}",
            **_DEFAULT_UPSTREAMS,
            **upstreams,
        }
        proc = subprocess.Popen(
            [caddy, "run", "--config", str(CADDYFILE), "--adapter", "caddyfile"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        processes.append(proc)
        if not _wait_until_listening(port):
            proc.terminate()
            output = proc.communicate(timeout=5)[0].decode(errors="replace")
            raise RuntimeError(
                f"gateway did not start listening on port {port}:\n{output}"
            )
        return f"http://127.0.0.1:{port}"

    yield _start

    for proc in processes:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
