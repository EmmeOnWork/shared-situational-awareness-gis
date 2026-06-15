/**
 * URL persistence for the Active Vocazione (Slice 3, ADR-0005) — a COPIED module
 * in this independent deployable, mirroring reuse-service's `selection-url` against
 * the generalized per-axis selection bus.
 *
 * The Selector owns persistence: it reflects the chosen Vocazione's stable `slug`
 * into a `?vocazione=<slug>` query param (so the dashboard URL describes "the
 * dashboard focused on this Vocazione" — bookmarkable / shareable), and on load
 * restores the selection from that param by re-using the publish path. Consumers
 * stay oblivious; they only see the bus.
 *
 * The host URL bar is behind a tiny injectable seam so the contract is testable with
 * a fake, exactly like `SelectionBus`. The real adapter wraps `window.location` +
 * `history.replaceState` (replace, not push: a selection refines the current view, it
 * is not a new navigation).
 */

import { publishSelection, type SelectionBus } from "./selection-bus.ts";
import { findVocazione, type Vocazione } from "./vocazioni.ts";

/** The query param carrying the Active Vocazione's stable slug. */
export const VOCAZIONE_PARAM = "vocazione";

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
 * Reflect the chosen `slug` into the URL query param, in place (no navigation /
 * reload), preserving other existing params. A `null` slug is the "Tutte le
 * vocazioni" / show-all clear: the param is REMOVED entirely, so a shared link of an
 * unfiltered dashboard is genuinely unfiltered.
 */
export function reflectSelectionInUrl(slug: string | null, bar: UrlBar): void {
    const url = bar.readUrl();
    if (slug === null) url.searchParams.delete(VOCAZIONE_PARAM);
    else url.searchParams.set(VOCAZIONE_PARAM, slug);
    bar.replace(url);
}

/**
 * Read the retained slug from the URL, or `undefined` when the param is absent. The
 * caller resolves it against the in-bundle catalog before publishing.
 */
export function readSelectedVocazione(bar: UrlBar): string | undefined {
    return bar.readUrl().searchParams.get(VOCAZIONE_PARAM) ?? undefined;
}

/**
 * Restore the Active Vocazione carried by the URL on load: resolve the param's slug
 * against the in-bundle 16 (`findVocazione`), then re-use the publish path so
 * already-mounted consumers re-emit-converge and late-joiners read the retained
 * value. Returns the restored Vocazione so the Selector can label the trigger and
 * mark its option, or `undefined` when there is nothing to restore — no param, or a
 * slug not in the catalog (a stale/shared link degrades cleanly: no event, no
 * retained value, no false selection).
 */
export function restoreVocazione(
    bar: UrlBar,
    target: SelectionBus = window,
): Vocazione | undefined {
    const slug = readSelectedVocazione(bar);
    if (slug === undefined) return undefined;
    const vocazione = findVocazione(slug);
    if (!vocazione) return undefined;
    publishSelection<Vocazione>("vocazione", vocazione, target);
    return vocazione;
}
