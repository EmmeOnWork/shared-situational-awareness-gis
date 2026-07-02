/**
 * Tests for the Scala Likert gauge mapping — the pure logic behind the needle,
 * emoji and label. No DOM (the SVG/markup is built in the element and covered by
 * typecheck). A Gradimento value ∈ [1,5] maps linearly to a needle position
 * ∈ [0,1]; five fixed buckets drive the emoji + one-word label; the review count
 * decides the low-confidence fade. Boundaries are half-open [lo, hi) so each edge
 * value (1.8 / 2.6 / 3.4 / 4.2) belongs to the HIGHER bucket.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { toScale } from "./scale.ts";

test("position maps value 1..5 linearly to 0..1 (1=left, 3=centre, 5=right)", () => {
    assert.equal(toScale(1, 100).position, 0);
    assert.equal(toScale(3, 100).position, 0.5);
    assert.equal(toScale(5, 100).position, 1);
});

test("position is monotonic increasing across the range", () => {
    const values = [1, 2, 3, 4, 5];
    const positions = values.map((v) => toScale(v, 100).position);
    for (let i = 1; i < positions.length; i++) {
        assert.ok(positions[i] > positions[i - 1], `position should rise at ${values[i]}`);
    }
});

test("each of the five buckets maps to its emoji + one-word label", () => {
    assert.deepEqual(pick(toScale(1.0, 100)), { emoji: "😡", label: "Per niente gradito" });
    assert.deepEqual(pick(toScale(2.0, 100)), { emoji: "🙁", label: "Poco gradito" });
    assert.deepEqual(pick(toScale(3.0, 100)), { emoji: "😐", label: "Nella media" });
    assert.deepEqual(pick(toScale(3.8, 100)), { emoji: "🙂", label: "Gradito" });
    assert.deepEqual(pick(toScale(5.0, 100)), { emoji: "😍", label: "Molto gradito" });
});

test("bucket boundaries are half-open: each edge belongs to the higher bucket", () => {
    // just below the edge → lower bucket; exactly at the edge → higher bucket.
    assert.equal(toScale(1.79, 100).label, "Per niente gradito");
    assert.equal(toScale(1.8, 100).label, "Poco gradito");
    assert.equal(toScale(2.6, 100).label, "Nella media");
    assert.equal(toScale(3.4, 100).label, "Gradito");
    assert.equal(toScale(4.2, 100).label, "Molto gradito");
});

test("lowConfidence is true below the review FLOOR (15) and false at/above it", () => {
    assert.equal(toScale(4.2, 14).lowConfidence, true);
    assert.equal(toScale(4.2, 15).lowConfidence, false);
    assert.equal(toScale(4.2, 100).lowConfidence, false);
});

test("colour differs between the red (low) and green (high) ends", () => {
    const low = toScale(1, 100).color;
    const high = toScale(5, 100).color;
    assert.equal(typeof low, "string");
    assert.notEqual(low, high);
});

function pick(s: { emoji: string; label: string }) {
    return { emoji: s.emoji, label: s.label };
}
