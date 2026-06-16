/**
 * Contract tests for the Notifier's pure audio core (slice 4).
 *
 * Zero-dependency: Node's built-in test runner, no DOM / Web Audio. The
 * AudioContext, the first-gesture unlock, and the actual oscillator playback in
 * NotifierAudio are host-coupled glue covered by typecheck + manual verification
 * (PRD testing decisions, ADR-0004). What is pinned here is the DOM-free thing
 * the playback is built on — the severity→sound mapping, the audio analogue of
 * Slice 2's SEVERITY_COLOUR: the three severities are audibly distinct and
 * `success` is clearly celebratory.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { toneSequence } from "./audio.ts";

import type { Severity } from "./notification.ts";

test("each severity yields a non-empty tone sequence", () => {
    assert.ok(toneSequence("info").length > 0);
    assert.ok(toneSequence("warning").length > 0);
    assert.ok(toneSequence("success").length > 0);
});

test("the three severities are mutually distinct sound sequences", () => {
    const severities: Severity[] = ["info", "warning", "success"];
    const sounds = severities.map((s) => JSON.stringify(toneSequence(s)));

    assert.equal(new Set(sounds).size, severities.length, "no two severities share a sound");
});

test("warning is a double tone: two notes at the same pitch, unlike info's single note", () => {
    const warning = toneSequence("warning");

    assert.equal(toneSequence("info").length, 1);
    assert.equal(warning.length, 2);
    assert.equal(warning[0].freq, warning[1].freq, "the double tone repeats one pitch");
    assert.ok(warning[1].startMs > warning[0].startMs, "the second tone follows the first");
});

test("success is celebratory: more notes than info and pitch strictly ascending", () => {
    const success = toneSequence("success");

    assert.ok(success.length > toneSequence("info").length);
    for (let i = 1; i < success.length; i++) {
        assert.ok(success[i].freq > success[i - 1].freq, "each note rises in pitch");
    }
});
