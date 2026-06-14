/**
 * Active Workshop client — the SUBSCRIBER half of the page-global selection bus
 * (ADR-0003). The reuse-service `<reuse-widget>` publishes the Active Workshop;
 * this characteristic widget is the first "sensitive" widget that consumes it.
 *
 * Mirrors the publisher's contract exactly (event name + `detail` shape) so the
 * two halves stay coupled only to the contract, never to each other. A sensitive
 * widget converges however it joins:
 *   - reads the RETAINED last value at mount (late mount / HMR remount);
 *   - SUBSCRIBES for subsequent selections.
 * `target` is injectable so the contract is testable against a fake bus.
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
 * Read the retained Active Workshop at mount, or `undefined` if none was published
 * yet. Lets a late-joining / HMR-remounted widget converge without waiting for the
 * next selection event (ADR-0003).
 */
export function readActiveWorkshop(target: WorkshopBus = window): ActiveWorkshop | undefined {
    return target.__praimActiveWorkshop;
}

/**
 * Subscribe to Active Workshop selections; `handler` is called with the published
 * Bene on every `praim:workshop-selected`. Returns an unsubscribe function so the
 * element can detach on `disconnectedCallback`.
 */
export function subscribeActiveWorkshop(
    handler: (workshop: ActiveWorkshop) => void,
    target: WorkshopBus = window,
): () => void {
    const listener = (e: Event) => handler((e as CustomEvent<ActiveWorkshop>).detail);
    target.addEventListener(WORKSHOP_EVENT, listener);
    return () => target.removeEventListener(WORKSHOP_EVENT, listener);
}
