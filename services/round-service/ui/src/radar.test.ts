/**
 * Tests for the recap radar geometry — the pure maths behind the phase-3 chart.
 *
 * The radar draws one spoke per stakeholder Role present in the Round, the data
 * vertex placed along that spoke at a distance proportional to the Role's
 * intra-Role Consensus (0 → centre, 1 → rim). These assert that geometry and the
 * "consenso totale" percent label, with no DOM (rendering is typecheck-covered).
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { radarVertices, consensoTotalePct } from "./radar.ts";

const CX = 100;
const CY = 100;
const R = 80;

test("consensoTotalePct renders the pooled overall as a whole percent", () => {
    assert.equal(consensoTotalePct(0.6137466), "61%");
    assert.equal(consensoTotalePct(1), "100%");
    assert.equal(consensoTotalePct(0), "0%");
});

test("a unanimous branch reaches the rim; a dispersed branch sits at the centre", () => {
    const [full] = radarVertices([{ role: "istituzionale", consensus: 1 }], CX, CY, R);
    const [none] = radarVertices([{ role: "tecnico", consensus: 0 }], CX, CY, R);

    // One branch → its spoke points straight up; consensus=1 is R above centre.
    assert.ok(Math.abs(full.x - CX) < 1e-9);
    assert.ok(Math.abs(full.y - (CY - R)) < 1e-9);
    // consensus=0 collapses onto the centre regardless of angle.
    assert.ok(Math.abs(none.x - CX) < 1e-9);
    assert.ok(Math.abs(none.y - CY) < 1e-9);
});

test("there is exactly one vertex per Role present, evenly spaced", () => {
    const verts = radarVertices(
        [
            { role: "istituzionale", consensus: 1 },
            { role: "economico", consensus: 1 },
            { role: "tecnico", consensus: 1 },
            { role: "sociale", consensus: 1 },
        ],
        CX,
        CY,
        R,
    );

    assert.equal(verts.length, 4);
    // Four evenly spaced spokes at full consensus → the four cardinal points.
    const second = verts[1]; // 90° clockwise from top → straight right
    assert.ok(Math.abs(second.x - (CX + R)) < 1e-9);
    assert.ok(Math.abs(second.y - CY) < 1e-9);
});
