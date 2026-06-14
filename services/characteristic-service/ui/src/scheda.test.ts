/**
 * Unit tests for the Scheda view/serialise helpers — the two pieces of genuine
 * logic the element leans on (the rest is rendering, covered by typecheck/build).
 *
 * `isSchedaEmpty` decides State 4: a Blueprint clicked when the Scheda is empty
 * shows "non disponibile", not blank fields. `buildSchedaPayload` turns the raw
 * form values into the PUT body, dropping empties so an untouched form posts an
 * (empty, valid) Scheda — the optional/non-blocking rule.
 *
 * Zero-dependency: Node's built-in test runner, no DOM (these are pure functions).
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { isSchedaEmpty, buildSchedaPayload, type Scheda } from "./scheda.ts";

test("isSchedaEmpty is true for a null Scheda (never filled)", () => {
    assert.equal(isSchedaEmpty(null), true);
});

test("isSchedaEmpty is true when every field is blank or an empty array", () => {
    assert.equal(isSchedaEmpty({ denominazione: "", titolo: "", vincoli: [] }), true);
});

test("isSchedaEmpty is false once any field carries a value", () => {
    assert.equal(isSchedaEmpty({ denominazione: "Ex Macello" }), false);
    assert.equal(isSchedaEmpty({ vincoli: ["paesaggistico"] }), false);
});

test("buildSchedaPayload trims text and drops empty fields", () => {
    const payload = buildSchedaPayload(
        { denominazione: "  Ex Macello  ", titolo: "proprieta", foglio: "   " },
        [],
    );

    assert.deepEqual(payload, { denominazione: "Ex Macello", titolo: "proprieta" });
});

test("buildSchedaPayload includes vincoli only when some are checked", () => {
    assert.deepEqual(buildSchedaPayload({}, ["paesaggistico", "culturale"]), {
        vincoli: ["paesaggistico", "culturale"],
    });
    // No vincoli checked -> the field is omitted, not sent as an empty array.
    assert.deepEqual(buildSchedaPayload({}, []), {});
});

test("buildSchedaPayload of an untouched form is an empty (valid) Scheda", () => {
    const payload: Scheda = buildSchedaPayload(
        { denominazione: "", titolo: "", referente_email: "" },
        [],
    );

    assert.deepEqual(payload, {});
});
