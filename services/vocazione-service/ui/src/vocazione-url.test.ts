/**
 * Contract tests for URL persistence of the Active Vocazione (Slice 3, ADR-0005).
 *
 * The Selector owns persistence: the chosen Vocazione's stable `slug` is reflected
 * into a `?vocazione=<slug>` query param (so a focused dashboard is bookmarkable /
 * shareable), and on load the selection is restored from the URL by re-using the
 * publish path (retained value + re-emit). Clearing to "Tutte" removes the param so
 * a shared unfiltered link is genuinely unfiltered.
 *
 * Zero-dependency, mirroring the reuse-service `selection-url` tests: Node's test
 * runner, a fake URL bar, and a fake bus. No DOM/jsdom — the <vocazione-widget>
 * wiring is covered by typecheck.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
    reflectSelectionInUrl,
    readSelectedVocazione,
    restoreVocazione,
    VOCAZIONE_PARAM,
    type UrlBar,
} from "./vocazione-url.ts";
import { selectionEvent, type SelectionBus } from "./selection-bus.ts";
import { VOCAZIONI, type Vocazione } from "./vocazioni.ts";

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

/** A stand-in for the host `window`: an EventTarget carrying the retained per-axis map. */
class FakeBus extends EventTarget implements SelectionBus {
    __praimSelections?: Record<string, unknown>;
}

const VOCAZIONE_EVENT = selectionEvent("vocazione");
const KNOWN: Vocazione = VOCAZIONI[0]; // { id: "dimora-del-benessere", label: ... }

test("restoreVocazione resolves the URL slug to its Vocazione and re-publishes it", () => {
    const bar = new FakeUrlBar(`https://dash.example/board?${VOCAZIONE_PARAM}=${KNOWN.id}`);
    const bus = new FakeBus();
    let received: Vocazione | null | undefined;
    bus.addEventListener(VOCAZIONE_EVENT, (e) => {
        received = (e as CustomEvent<Vocazione | null>).detail;
    });

    const restored = restoreVocazione(bar, bus);

    // The full Vocazione is recovered from the in-bundle catalog and pushed through
    // the publish path:
    assert.deepEqual(restored, KNOWN);
    assert.deepEqual(received, KNOWN); // re-emitted for already-subscribed consumers
    assert.deepEqual(bus.__praimSelections?.vocazione, KNOWN); // retained for late-joiners
});

test("reflectSelectionInUrl writes the chosen slug to the URL query param", () => {
    const bar = new FakeUrlBar("https://dash.example/board");

    reflectSelectionInUrl(KNOWN.id, bar);

    assert.equal(new URL(bar.href).searchParams.get(VOCAZIONE_PARAM), KNOWN.id);
});

test("reflectSelectionInUrl preserves other existing query params (no clobber, no reload)", () => {
    const bar = new FakeUrlBar("https://dash.example/board?area=Torino&zoom=12");

    reflectSelectionInUrl(KNOWN.id, bar);

    const params = new URL(bar.href).searchParams;
    assert.equal(params.get(VOCAZIONE_PARAM), KNOWN.id);
    assert.equal(params.get("area"), "Torino");
    assert.equal(params.get("zoom"), "12");
});

test("reflectSelectionInUrl(null) removes the param entirely so a shared link is unfiltered", () => {
    const bar = new FakeUrlBar(`https://dash.example/board?${VOCAZIONE_PARAM}=${KNOWN.id}&area=Torino`);

    reflectSelectionInUrl(null, bar); // picking "Tutte le vocazioni"

    const params = new URL(bar.href).searchParams;
    assert.equal(params.has(VOCAZIONE_PARAM), false); // gone, not "" or "null"
    assert.equal(params.get("area"), "Torino"); // other params untouched
});

test("readSelectedVocazione returns the slug carried by the URL, undefined when absent", () => {
    assert.equal(
        readSelectedVocazione(new FakeUrlBar(`https://dash.example/board?${VOCAZIONE_PARAM}=${KNOWN.id}`)),
        KNOWN.id,
    );
    assert.equal(readSelectedVocazione(new FakeUrlBar("https://dash.example/board")), undefined);
});

test("restoreVocazione degrades cleanly on an unknown/stale slug — no event, nothing retained", () => {
    const bar = new FakeUrlBar(`https://dash.example/board?${VOCAZIONE_PARAM}=non-esiste`);
    const bus = new FakeBus();
    let emitted = false;
    bus.addEventListener(VOCAZIONE_EVENT, () => {
        emitted = true;
    });

    const restored = restoreVocazione(bar, bus);

    assert.equal(restored, undefined); // no false selection
    assert.equal(emitted, false); // no event for a Vocazione not in the catalog
    assert.equal(bus.__praimSelections?.vocazione, undefined); // nothing retained
});

test("restoreVocazione degrades cleanly when there is no param at all", () => {
    const bar = new FakeUrlBar("https://dash.example/board");
    const bus = new FakeBus();
    let emitted = false;
    bus.addEventListener(VOCAZIONE_EVENT, () => {
        emitted = true;
    });

    const restored = restoreVocazione(bar, bus);

    assert.equal(restored, undefined);
    assert.equal(emitted, false);
    assert.equal(bus.__praimSelections?.vocazione, undefined);
});
