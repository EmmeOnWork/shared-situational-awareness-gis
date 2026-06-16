/**
 * Contract tests for the Notifier's pure frontend seams (slice 2).
 *
 * Zero-dependency: Node's built-in test runner, no DOM/jsdom. The toast DOM and
 * WebSocket wiring in <notification-overlay> are host-coupled glue covered by
 * typecheck + manual verification (ADR-0004); what is pinned here is the pure
 * logic the toast is built on — the severity→colour map, the ws:// URL the
 * client connects to, and the parse that rejects anything that is not a
 * well-formed Notification.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { SEVERITY_COLOUR, notifierWsUrl, parseNotification } from "./notification.ts";

test("each severity maps to its toast colour", () => {
    assert.equal(SEVERITY_COLOUR.info, "#2563eb"); // blue
    assert.equal(SEVERITY_COLOUR.warning, "#d97706"); // amber
    assert.equal(SEVERITY_COLOUR.success, "#16a34a"); // green
});

test("notifierWsUrl derives ws:// from an http origin and carries the token", () => {
    assert.equal(
        notifierWsUrl("http://localhost:8080", "tok123"),
        "ws://localhost:8080/notifications/ws?access_token=tok123",
    );
});

test("notifierWsUrl derives wss:// from an https origin", () => {
    assert.equal(
        notifierWsUrl("https://praim.example", "abc"),
        "wss://praim.example/notifications/ws?access_token=abc",
    );
});

test("parseNotification accepts a well-formed Notification", () => {
    const n = parseNotification(
        JSON.stringify({ severity: "warning", title: "Round chiuso", body: "Tutti hanno votato" }),
    );

    assert.deepEqual(n, { severity: "warning", title: "Round chiuso", body: "Tutti hanno votato" });
});

test("parseNotification rejects an unknown severity", () => {
    const n = parseNotification(JSON.stringify({ severity: "critical", title: "x", body: "y" }));

    assert.equal(n, null);
});

test("parseNotification rejects a payload missing title or body", () => {
    assert.equal(parseNotification(JSON.stringify({ severity: "info", title: "x" })), null);
    assert.equal(parseNotification("not json"), null);
});

test("parseNotification carries a well-formed scope through to the filter", () => {
    const n = parseNotification(
        JSON.stringify({
            severity: "warning",
            title: "Round chiuso",
            body: "Tutti hanno votato",
            scope: { axis: "workshop", value: "42" },
        }),
    );

    assert.deepEqual(n, {
        severity: "warning",
        title: "Round chiuso",
        body: "Tutti hanno votato",
        scope: { axis: "workshop", value: "42" },
    });
});

test("parseNotification rejects a malformed scope (missing value)", () => {
    const n = parseNotification(
        JSON.stringify({ severity: "info", title: "x", body: "y", scope: { axis: "workshop" } }),
    );

    assert.equal(n, null);
});
