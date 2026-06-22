/**
 * Contract tests for the Active Workshop client (ADR-0003) — the SUBSCRIBER half.
 *
 * The Round Manager is a "sensitive" widget: it converges on the Active Workshop
 * the reuse-service publisher emits (it consumes, never publishes). These assert
 * the client reads the retained last value at mount and re-renders on the
 * `praim:workshop-selected` event — exercised against the SAME contract the
 * publisher emits (event name + `{poiId, lat, lng, name}` detail), so they survive
 * any refactor of the element. No Active Workshop ⇒ empty state ("seleziona un
 * Bene"); a selection ⇒ that Bene's lobby placeholder.
 *
 * Zero-dependency: Node's built-in test runner + a fake EventTarget. No DOM/jsdom;
 * the element's rendering is covered by typecheck, not by these tests (by design).
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
    readActiveWorkshop,
    subscribeActiveWorkshop,
    WORKSHOP_EVENT,
    type ActiveWorkshop,
} from "./active-workshop-client.ts";

/** A stand-in for the host `window`: an EventTarget carrying the retained value. */
class FakeBus extends EventTarget {
    __praimActiveWorkshop?: ActiveWorkshop;
}

const SAMPLE: ActiveWorkshop = { poiId: 42, lat: 45.07, lng: 7.69, name: "Ex Macello" };

test("readActiveWorkshop is undefined when no Bene is selected (empty state)", () => {
    const bus = new FakeBus();

    assert.equal(readActiveWorkshop(bus), undefined);
});

test("readActiveWorkshop returns the retained Active Workshop at mount (late-join/HMR)", () => {
    const bus = new FakeBus();
    bus.__praimActiveWorkshop = SAMPLE; // set as if the Selector published before we mounted

    assert.deepEqual(readActiveWorkshop(bus), SAMPLE);
});

test("subscribeActiveWorkshop swaps to the selected Bene on praim:workshop-selected", () => {
    const bus = new FakeBus();
    let received: ActiveWorkshop | undefined;
    const unsubscribe = subscribeActiveWorkshop((w) => {
        received = w;
    }, bus);

    // Dispatched exactly as the reuse-service publisher emits it (same contract).
    bus.dispatchEvent(new CustomEvent<ActiveWorkshop>(WORKSHOP_EVENT, { detail: SAMPLE }));
    assert.deepEqual(received, SAMPLE);

    // The returned unsubscribe stops further callbacks (clean teardown on disconnect).
    received = undefined;
    unsubscribe();
    bus.dispatchEvent(new CustomEvent<ActiveWorkshop>(WORKSHOP_EVENT, { detail: SAMPLE }));
    assert.equal(received, undefined);
});
