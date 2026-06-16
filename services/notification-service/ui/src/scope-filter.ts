/**
 * scope-filter — the pure show/suppress decision for a Notification (slice 5).
 *
 * The server broadcasts every Notification to everyone (ADR-0006: overlays are
 * page-global, so scoping is a client-side filter, never server-side rooms). This
 * is where each client suppresses what is not for it: a scoped Notification reaches
 * only the participants whose current selection on that axis matches, so people are
 * not interrupted by events about a different Bene.
 *
 * Deep & pure: no DOM, no bus. The <notification-overlay> glue resolves the client's
 * current selection on `notification.scope.axis` from the selection bus and passes
 * it here as `currentSelection` (or undefined/null when nothing is selected).
 */

import type { Notification } from "./notification.ts";

/**
 * Decide whether to render `notification` given the client's `currentSelection` on
 * the notification's scope axis:
 *   - an UNSCOPED Notification always renders;
 *   - a SCOPED Notification renders only when `scope.value` matches the current
 *     selection, and is suppressed on mismatch;
 *   - a SCOPED Notification is suppressed when there is no current selection
 *     (`undefined` not-yet-published, or `null` explicitly cleared).
 */
export function shouldRender(
    notification: Notification,
    currentSelection: string | null | undefined,
): boolean {
    const scope = notification.scope;
    if (!scope) return true;
    if (currentSelection == null) return false;
    return scope.value === currentSelection;
}
