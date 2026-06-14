/**
 * URL persistence for the Active Workshop (Slice 3, ADR-0003).
 *
 * The Workshop Selector owns persistence: it reflects the chosen Bene's `poiId` into
 * a URL query param (so the dashboard URL describes "the dashboard for this building"
 * — bookmarkable / shareable), and on load restores the selection from that param by
 * re-using the publish path. Sensitive widgets stay oblivious; they only see the bus.
 *
 * The host URL bar is behind a tiny injectable seam so the contract is testable with a
 * fake, exactly like `WorkshopBus`. The real adapter wraps `window.location` +
 * `history.replaceState` (replace, not push: a selection refines the current view, it
 * is not a new navigation).
 */

import {
    publishActiveWorkshop,
    type ActiveWorkshop,
    type WorkshopBus,
} from "./active-workshop.ts";

/** The query param carrying the Active Workshop's `poiId`. */
export const POI_PARAM = "poiId";

/** Minimal view of the host URL bar: read the current URL, replace it without navigating. */
export interface UrlBar {
    readUrl(): URL;
    replace(url: URL): void;
}

/**
 * The real host URL bar: reads `window.location` and updates it with
 * `history.replaceState` — same URL, refined query, no navigation/reload. The
 * injectable seam above lets tests swap a fake for this without a DOM.
 */
export const hostUrlBar: UrlBar = {
    readUrl: () => new URL(window.location.href),
    replace: (url) => history.replaceState(history.state, "", url.href),
};

/**
 * Reflect `poiId` into the URL query param, in place (no full navigation / reload).
 * Other existing params are preserved — selection refines the current dashboard URL.
 */
export function reflectSelectionInUrl(poiId: number, bar: UrlBar): void {
    const url = bar.readUrl();
    url.searchParams.set(POI_PARAM, String(poiId));
    bar.replace(url);
}

/**
 * Read the retained `poiId` from the URL, or `undefined` when the param is absent or
 * not a number. The caller resolves it against the loaded Bene list before publishing.
 */
export function readSelectedPoiId(bar: UrlBar): number | undefined {
    const raw = bar.readUrl().searchParams.get(POI_PARAM);
    if (raw === null) return undefined;
    const poiId = Number(raw);
    return Number.isFinite(poiId) ? poiId : undefined;
}

/**
 * Restore the Active Workshop carried by the URL on load: resolve the param's `poiId`
 * against the loaded `benes`, then re-use the publish path so already-mounted widgets
 * re-emit-converge and late-joiners read the retained value. Returns the restored Bene
 * so the Selector can mark its row active, or `undefined` when there is nothing to
 * restore — no param, or a `poiId` not in the list (a stale/shared link degrades
 * cleanly: no event, no retained value, no false selection).
 */
export function restoreActiveWorkshop(
    benes: ActiveWorkshop[],
    bar: UrlBar,
    target: WorkshopBus = window,
): ActiveWorkshop | undefined {
    const poiId = readSelectedPoiId(bar);
    if (poiId === undefined) return undefined;
    const bene = benes.find((b) => b.poiId === poiId);
    if (!bene) return undefined;
    publishActiveWorkshop(bene, target);
    return bene;
}
