/**
 * Contract tests for current-selection — resolving the receiver's current selection
 * id from the two selection buses that coexist (ADR-0005). The regression these pin:
 * the workshop axis is published on the LEGACY `__praimActiveWorkshop` global, so
 * reading only the generalized `__praimSelections` map made the overlay suppress
 * EVERY workshop-scoped Notification (round opened / closed / consensus). Zero-
 * dependency (node:test, no DOM): the bus realm is injected as a fake.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { currentSelectionId, type SelectionRealm } from "./current-selection.ts";

const realm = (r: unknown): SelectionRealm => r as SelectionRealm;

test("workshop axis resolves the LEGACY Active Workshop's poiId (the bug fix)", () => {
    const bus = realm({ __praimActiveWorkshop: { poiId: 42, lat: 0, lng: 0, name: "Bene" } });
    assert.equal(currentSelectionId("workshop", bus), "42");
});

test("workshop axis is undefined when no Active Workshop has been published", () => {
    assert.equal(currentSelectionId("workshop", realm({})), undefined);
});

test("the generalized per-axis map takes precedence (forward-compatible once migrated)", () => {
    const bus = realm({
        __praimSelections: { workshop: { poiId: 7 } },
        __praimActiveWorkshop: { poiId: 42 },
    });
    assert.equal(currentSelectionId("workshop", bus), "7");
});

test("a non-workshop axis reads the generalized map and stringifies a scalar value", () => {
    const bus = realm({ __praimSelections: { vocazione: "edilizia" } });
    assert.equal(currentSelectionId("vocazione", bus), "edilizia");
});

test("an explicitly cleared (null) generalized selection passes through as null", () => {
    const bus = realm({ __praimSelections: { vocazione: null } });
    assert.equal(currentSelectionId("vocazione", bus), null);
});
