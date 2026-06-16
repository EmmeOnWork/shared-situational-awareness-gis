/**
 * The Notifier's pure frontend contract — no DOM, no WebSocket.
 *
 * Mirrors the backend wire contract (`src/notifier/notification.py`): a
 * self-describing alert carrying only a presentation `severity` + text, and an
 * optional `scope`. Kept DOM-free so it is unit-testable with `node:test`; the
 * <notification-overlay> element composes these into the toast + connection.
 */

export type Severity = "info" | "warning" | "success";

export interface Notification {
    severity: Severity;
    title: string;
    body: string;
    scope?: { axis: string; value: string };
}

/** severity → toast colour. The only domain-ish vocabulary the Notifier knows. */
export const SEVERITY_COLOUR: Record<Severity, string> = {
    info: "#2563eb", // blue
    warning: "#d97706", // amber
    success: "#16a34a", // green
};

/**
 * The WebSocket URL this client subscribes to, derived from the host `base`
 * origin: http→ws, https→wss, same path, with the host JWT as `?access_token=`,
 * which the server verifies on the handshake (slice 3). `base` is the edge-gateway
 * origin the host feeds the element.
 */
export function notifierWsUrl(base: string, token: string): string {
    const wsBase = base.replace(/^http/, "ws");
    return `${wsBase}/notifications/ws?access_token=${encodeURIComponent(token)}`;
}

/**
 * Parse one inbound WS frame into a Notification, or `null` if it is not a
 * well-formed one. The client renders only what survives this — a malformed or
 * mis-severity'd frame is dropped, never toasted (defence in depth alongside the
 * server's pydantic validation).
 */
export function parseNotification(raw: string): Notification | null {
    let data: unknown;
    try {
        data = JSON.parse(raw);
    } catch {
        return null;
    }
    if (typeof data !== "object" || data === null) return null;
    const { severity, title, body, scope } = data as Record<string, unknown>;
    if (severity !== "info" && severity !== "warning" && severity !== "success") return null;
    if (typeof title !== "string" || typeof body !== "string") return null;

    const notification: Notification = { severity, title, body };

    // `scope` is optional, but when present it must be well-formed (axis+value
    // strings) — a half-formed scope is dropped with the whole frame, never toasted
    // unscoped, so client-side scope filtering can rely on it (slice 5).
    if (scope !== undefined) {
        if (typeof scope !== "object" || scope === null) return null;
        const { axis, value } = scope as Record<string, unknown>;
        if (typeof axis !== "string" || typeof value !== "string") return null;
        notification.scope = { axis, value };
    }

    return notification;
}
