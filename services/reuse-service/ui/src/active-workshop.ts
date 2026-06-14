/**
 * Active Workshop publisher — the page-global selection bus (ADR-0003).
 *
 * The Workshop Selector (<reuse-widget>) calls this when the user picks a Bene.
 * It broadcasts the choice as a `praim:workshop-selected` CustomEvent on the host
 * `window`, so every "sensitive" widget that subscribes converges on the same
 * Active Workshop — without any per-widget plumbing or a monolith edit. Widgets
 * couple only to this contract (the `detail` shape), never to the Selector.
 */

/** The single page-global event name carrying the Active Workshop. */
export const WORKSHOP_EVENT = "praim:workshop-selected";

/** The Active Workshop contract: the selected Bene, as the bus carries it. */
export interface ActiveWorkshop {
    poiId: number;
    lat: number;
    lng: number;
    name: string;
}

/**
 * The host realm seen as the Active Workshop bus: an EventTarget that also holds
 * the retained last value. `window` satisfies this at runtime; tests pass a fake.
 */
export interface WorkshopBus extends EventTarget {
    __praimActiveWorkshop?: ActiveWorkshop;
}

/**
 * Publish `workshop` as the current Active Workshop on `target` (defaults to the
 * host `window`). Does two things so a sensitive widget converges however it joins:
 *   - sets the **retained last value** for widgets that read at mount (late / HMR);
 *   - **dispatches** the event for widgets already subscribed.
 * `target` is injectable so the contract is testable against a fake bus.
 */
export function publishActiveWorkshop(
    workshop: ActiveWorkshop,
    target: WorkshopBus = window,
): void {
    target.__praimActiveWorkshop = workshop;
    target.dispatchEvent(new CustomEvent<ActiveWorkshop>(WORKSHOP_EVENT, { detail: workshop }));
}
