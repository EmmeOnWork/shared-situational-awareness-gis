/**
 * Generalized cross-widget selection bus (ADR-0005) — a COPIED helper in this
 * independent deployable (no shared package, consistent with the strangler
 * architecture and the existing copy pattern across the Widgets).
 *
 * The Notifier only ever READS this bus: on each received Notification it consults
 * the receiver's current selection on the Notification's `scope.axis` (the
 * `workshop` axis = the Active Workshop / selected Bene) to decide show vs suppress
 * (slice 5). It never publishes or owns the selection — that is the Workshop
 * Selector's (reuse-service).
 *
 * Per-axis contract: each selection axis gets its own event `praim:selection:<axis>`
 * and its own slot in a retained `window.__praimSelections[axis]` map. `null` is the
 * explicit CLEARED value; `undefined` (from `readSelection`) means nothing was ever
 * published on that axis — both suppress a scoped Notification. `target` is injectable
 * so the contract is testable against a fake bus.
 */

/** The selection axes carried on the bus; extensible to N axes. */
export type SelectionAxis = "workshop" | "vocazione";

/**
 * The host realm seen as the selection bus: an EventTarget that also holds the
 * retained per-axis map. `window` satisfies this at runtime; tests pass a fake.
 */
export interface SelectionBus extends EventTarget {
    __praimSelections?: Partial<Record<SelectionAxis, unknown>>;
}

/** The per-axis event name carrying that axis's value (or `null` when cleared). */
export const selectionEvent = (axis: SelectionAxis): string => `praim:selection:${axis}`;

/**
 * Subscribe to selections on `axis`; `handler` is called with the published value
 * (or `null` when cleared) on every change. Returns an unsubscribe function so the
 * consumer can detach on `disconnectedCallback`.
 */
export function subscribeSelection<T>(
    axis: SelectionAxis,
    handler: (value: T | null) => void,
    target: SelectionBus = window,
): () => void {
    const listener = (e: Event) => handler((e as CustomEvent<T | null>).detail);
    target.addEventListener(selectionEvent(axis), listener);
    return () => target.removeEventListener(selectionEvent(axis), listener);
}

/**
 * Read the retained value on `axis` at mount: the last published value, `null` if it
 * was explicitly cleared, or `undefined` if nothing was ever published on that axis.
 * Lets a late-joining / HMR-remounted consumer converge without waiting for the next
 * change.
 */
export function readSelection<T>(
    axis: SelectionAxis,
    target: SelectionBus = window,
): T | null | undefined {
    return target.__praimSelections?.[axis] as T | null | undefined;
}
