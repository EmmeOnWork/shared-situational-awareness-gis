/**
 * Contract tests for URL persistence of the Active Workshop (Slice 3, ADR-0003).
 *
 * The Selector owns persistence: the chosen Bene's `poiId` is reflected into a URL
 * query param so the dashboard is bookmarkable/shareable, and on load the selection
 * is restored from the URL by re-using the publish path (retained value + re-emit).
 *
 * Zero-dependency like the publisher tests: Node's test runner, a fake URL bar, and
 * the same FakeBus. No DOM/jsdom — the <reuse-widget> wiring is covered by typecheck.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
    reflectSelectionInUrl,
    readSelectedPoiId,
    restoreActiveWorkshop,
    POI_PARAM,
    type UrlBar,
} from "./selection-url.ts";
import { WORKSHOP_EVENT, type ActiveWorkshop } from "./active-workshop.ts";

/** A stand-in for the host URL bar: holds an href, replaced in place (no navigation). */
class FakeUrlBar implements UrlBar {
    href: string;
    constructor(href: string) {
        this.href = href;
    }
    readUrl(): URL {
        return new URL(this.href);
    }
    replace(url: URL): void {
        this.href = url.href;
    }
}

/** A stand-in for the host `window`: an EventTarget that can carry the retained value. */
class FakeBus extends EventTarget {
    __praimActiveWorkshop?: ActiveWorkshop;
}

const BENES: ActiveWorkshop[] = [
    { poiId: 42, lat: 45.07, lng: 7.69, name: "Ex Macello" },
    { poiId: 7, lat: 45.06, lng: 7.68, name: "Cavallerizza" },
];

test("reflectSelectionInUrl writes the chosen poiId to the URL query param", () => {
    const bar = new FakeUrlBar("https://dash.example/board");

    reflectSelectionInUrl(42, bar);

    assert.equal(new URL(bar.href).searchParams.get(POI_PARAM), "42");
});

test("reflectSelectionInUrl preserves other existing query params (no clobber, no reload)", () => {
    const bar = new FakeUrlBar("https://dash.example/board?area=Torino&zoom=12");

    reflectSelectionInUrl(7, bar);

    const params = new URL(bar.href).searchParams;
    assert.equal(params.get(POI_PARAM), "7");
    assert.equal(params.get("area"), "Torino");
    assert.equal(params.get("zoom"), "12");
});

test("readSelectedPoiId returns the poiId carried by the URL, undefined when absent", () => {
    assert.equal(readSelectedPoiId(new FakeUrlBar("https://dash.example/board?poiId=42")), 42);
    assert.equal(readSelectedPoiId(new FakeUrlBar("https://dash.example/board")), undefined);
});

test("restoreActiveWorkshop resolves the URL poiId to the full Bene and re-publishes it", () => {
    const bar = new FakeUrlBar("https://dash.example/board?poiId=42");
    const bus = new FakeBus();
    let received: ActiveWorkshop | undefined;
    bus.addEventListener(WORKSHOP_EVENT, (e) => {
        received = (e as CustomEvent<ActiveWorkshop>).detail;
    });

    const restored = restoreActiveWorkshop(BENES, bar, bus);

    // The whole Bene detail is recovered from the list and pushed through the publish path:
    assert.deepEqual(restored, BENES[0]);
    assert.deepEqual(received, BENES[0]); // re-emitted for already-subscribed widgets
    assert.deepEqual(bus.__praimActiveWorkshop, BENES[0]); // retained for late-joiners
});

test("restoreActiveWorkshop degrades cleanly when the URL poiId is not a known Bene", () => {
    const bar = new FakeUrlBar("https://dash.example/board?poiId=999"); // stale / shared link
    const bus = new FakeBus();
    let emitted = false;
    bus.addEventListener(WORKSHOP_EVENT, () => {
        emitted = true;
    });

    const restored = restoreActiveWorkshop(BENES, bar, bus);

    assert.equal(restored, undefined); // no false selection
    assert.equal(emitted, false); // no event for a building that is not on the list
    assert.equal(bus.__praimActiveWorkshop, undefined); // nothing retained
});
