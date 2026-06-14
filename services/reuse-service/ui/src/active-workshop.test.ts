/**
 * Contract tests for the Active Workshop publisher (ADR-0003).
 *
 * The publisher is the source of truth for the `praim:workshop-selected` bus that
 * sensitive widgets (the characteristic-service client is the first) subscribe to.
 * These assert the *contract* — the event detail shape and the retained last value —
 * against a fake bus, so they survive any refactor of the <reuse-widget> internals.
 *
 * Zero-dependency: Node's built-in test runner + a fake EventTarget. No DOM/jsdom;
 * the widget click wiring is covered by typecheck, not by these tests (by design).
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import { publishActiveWorkshop, WORKSHOP_EVENT, type ActiveWorkshop } from "./active-workshop.ts";

/** A stand-in for the host `window`: an EventTarget that can carry the retained value. */
class FakeBus extends EventTarget {
    __praimActiveWorkshop?: ActiveWorkshop;
}

const SAMPLE: ActiveWorkshop = { poiId: 42, lat: 45.07, lng: 7.69, name: "Ex Macello" };

test("publishActiveWorkshop dispatches praim:workshop-selected with the Bene as detail", () => {
    const bus = new FakeBus();
    let received: ActiveWorkshop | undefined;
    bus.addEventListener(WORKSHOP_EVENT, (e) => {
        received = (e as CustomEvent<ActiveWorkshop>).detail;
    });

    publishActiveWorkshop(SAMPLE, bus);

    assert.deepEqual(received, SAMPLE);
});

test("publishActiveWorkshop sets the retained __praimActiveWorkshop so late-joiners converge", () => {
    const bus = new FakeBus();

    publishActiveWorkshop(SAMPLE, bus);

    // A sensitive widget mounting after the click reads this at mount (ADR-0003).
    assert.deepEqual(bus.__praimActiveWorkshop, SAMPLE);
});
