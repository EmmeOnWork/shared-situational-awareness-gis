/**
 * Contract tests for scope-filter (slice 5) — the pure show/suppress decision a
 * client makes against its own current selection, so a scoped Notification reaches
 * only participants looking at the Bene it concerns. The server still broadcasts to
 * everyone (ADR-0006: overlays are page-global → scoping is a client filter, never
 * server rooms); this is where each client suppresses what is not for it.
 *
 * Zero-dependency: Node's built-in test runner, no DOM. The bus read + the toast
 * wiring in <notification-overlay> are host-coupled glue covered by typecheck +
 * manual verification (ADR-0004); what is pinned here is the pure decision.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { shouldRender } from "./scope-filter.ts";
import type { Notification } from "./notification.ts";

const UNSCOPED: Notification = { severity: "info", title: "Tutti", body: "Annuncio globale" };

/** Scoped to the Bene with id 42 on the workshop axis (the receiver's Active Workshop). */
const SCOPED_42: Notification = {
    severity: "warning",
    title: "Round chiuso",
    body: "Tutti hanno votato",
    scope: { axis: "workshop", value: "42" },
};

test("an unscoped Notification always renders, regardless of the current selection", () => {
    assert.equal(shouldRender(UNSCOPED, undefined), true);
    assert.equal(shouldRender(UNSCOPED, "42"), true);
    assert.equal(shouldRender(UNSCOPED, null), true);
});

test("a scoped Notification renders when its scope.value matches the current selection", () => {
    assert.equal(shouldRender(SCOPED_42, "42"), true);
});

test("a scoped Notification is suppressed when viewing a different Bene (mismatch)", () => {
    assert.equal(shouldRender(SCOPED_42, "99"), false);
});

test("a scoped Notification is suppressed when there is no current selection on that axis", () => {
    assert.equal(shouldRender(SCOPED_42, undefined), false); // nothing ever published
    assert.equal(shouldRender(SCOPED_42, null), false); // explicitly cleared
});
