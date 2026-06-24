/**
 * current-selection — resolve the receiver's current selection on an axis to the
 * string id a Notification's `scope.value` is compared against (the slice-5 bus read,
 * lifted out of the host-coupled <notification-overlay> glue so it is unit-testable).
 *
 * It BRIDGES the two selection-bus conventions that coexist (ADR-0005): newer axes
 * use the generalized per-axis map (`window.__praimSelections[axis]`), but the
 * **workshop** axis is still published only on the LEGACY single-value bus
 * (`window.__praimActiveWorkshop`, ADR-0003) — that migration was deliberately
 * deferred. Reading only the generalized map therefore left the overlay blind to the
 * Active Workshop, so EVERY workshop-scoped Notification (round opened / closed /
 * consensus, published by the Round Manager) was silently suppressed — no toast, no
 * sound — even though the server delivered it. We prefer the generalized value (so
 * this stays correct once the workshop axis migrates) and fall back to the legacy
 * retained Active Workshop for the workshop axis.
 *
 * DOM-free: the bus realm is injected (defaulting to `window`), so this is testable
 * with node:test, unlike the connection/toast glue in <notification-overlay>.
 */

import { readSelection, type SelectionAxis, type SelectionBus } from "./selection-bus.ts";

/**
 * The host realm seen as BOTH selection buses: the generalized per-axis map and the
 * legacy `__praimActiveWorkshop` single value the workshop axis is still published
 * on. `window` satisfies this at runtime; tests pass a fake.
 */
export type SelectionRealm = SelectionBus & { __praimActiveWorkshop?: unknown };

/**
 * The retained selection value on `axis`: the generalized map's value when present,
 * else (for the workshop axis only) the legacy Active Workshop. `undefined` means
 * nothing was published on that axis; `null` is an explicit clear.
 */
export function resolveSelection(axis: SelectionAxis, realm: SelectionRealm = window): unknown {
    const generalized = readSelection<unknown>(axis, realm);
    if (generalized !== undefined) return generalized;
    return axis === "workshop" ? realm.__praimActiveWorkshop : undefined;
}

/**
 * The receiver's current selection on `axis` as the string id `scope.value` is
 * compared against. The Active Workshop is the selected Bene — its `poiId` (a Bene
 * IS a POI); a scalar axis value is already an id. `null`/`undefined` (cleared /
 * never selected) pass through so scope-filter suppresses the scoped Notification.
 */
export function currentSelectionId(
    axis: SelectionAxis,
    realm: SelectionRealm = window,
): string | null | undefined {
    const value = resolveSelection(axis, realm);
    if (value == null) return value as null | undefined;
    if (typeof value === "object" && "poiId" in value) {
        return String((value as { poiId: unknown }).poiId);
    }
    return String(value);
}
