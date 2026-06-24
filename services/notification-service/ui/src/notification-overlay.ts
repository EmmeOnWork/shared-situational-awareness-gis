/**
 * <notification-overlay> — the Realtime Notifier, shipped by notification-service
 * itself as a self-contained custom element.
 *
 * FRONTEND half of a full-stack Widget. Unlike every sibling Widget this is NOT
 * a grid card: the monolith's generic <RemoteOverlay> seam (ADR-0006) mounts it
 * **page-global and chromeless**, on top of the whole dashboard, from a catalog
 * row flagged `placement: "overlay"`.
 *
 * Contract with the host (same `token`/`base` the grid `remote` seam feeds card
 * Widgets, so the overlay seam mounts it identically):
 *   attribute `token` — the monolith-issued JWT; passed to the WS as
 *                       `?access_token=` and verified by the server on the
 *                       handshake (slice 3); re-read on every (re)connect so a
 *                       refreshed token re-authenticates transparently.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 *
 * THIS SLICE (5): before toasting/sounding, consult scope-filter against the
 * receiver's current Active Workshop (read from the selection bus, ADR-0005) so a
 * scoped Notification reaches only the participants looking at the Bene it concerns
 * — suppressed Notifications produce neither toast nor sound. The server still
 * broadcasts to everyone; this is a pure client-side filter (ADR-0006), no rooms.
 *
 * Earlier slices: render a top-right toast coloured by `severity` (slice 2) AND
 * play that severity's sound (slice 4, NotifierAudio); audio unlocks on the first
 * page-wide gesture. Slice 3 adds reconnect with capped exponential backoff after
 * an unexpected drop, each attempt re-reading the freshest host JWT.
 */

import { notifierWsUrl, parseNotification, SEVERITY_COLOUR } from "./notification.ts";
import { NotifierAudio } from "./audio.ts";
import { shouldRender } from "./scope-filter.ts";
import { currentSelectionId } from "./current-selection.ts";
import { type SelectionAxis } from "./selection-bus.ts";

const TOAST_TTL_MS = 5000;
// How long the fade-in / fade-out transition runs. Kept in sync with the CSS
// `transition` duration so a dismissed toast is removed from the DOM only after
// it has finished fading.
const TOAST_FADE_MS = 320;

class NotificationOverlay extends HTMLElement {
    static get observedAttributes() {
        return ["token", "base"];
    }

    private root: ShadowRoot;
    private socket?: WebSocket;
    private toasts!: HTMLElement;
    private audio = new NotifierAudio();

    // Reconnect/backoff state (slice 3). `closing` distinguishes an intentional
    // teardown (unmount / re-point) — which must NOT trigger a reconnect — from an
    // unexpected drop, which must. `backoffMs` grows per failed attempt and resets
    // on a successful open. `reconnectTimer` is the pending retry, cancellable.
    private closing = false;
    private backoffMs = 0;
    private reconnectTimer?: ReturnType<typeof setTimeout>;

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        // `:host { display: contents }` keeps the element itself off the layout;
        // the toast stack is a fixed, top-right, click-through container that only
        // ever holds transient toasts.
        this.root.innerHTML = `
            <style>
                :host { display: contents; }
                .stack {
                    /* Top aligned just below where the dashboard widgets start (the
                       4rem navbar + the page header bar), same right edge as before. */
                    position: fixed; top: 8.25rem; right: 1rem; z-index: 2147483647;
                    display: flex; flex-direction: column; gap: .75rem;
                    pointer-events: none; font-family: system-ui, sans-serif;
                }
                .toast {
                    pointer-events: auto; position: relative;
                    min-width: 22rem; max-width: 30rem;
                    color: #fff; border-radius: .75rem; padding: 1.1rem 1.4rem;
                    box-shadow: 0 6px 18px rgba(0,0,0,.28);
                    /* Fade + slide: starts hidden, .show fades it in, .hide fades it
                       out (TTL or the X). Duration mirrors TOAST_FADE_MS. */
                    opacity: 0; transform: translateX(.75rem);
                    transition: opacity ${TOAST_FADE_MS}ms ease, transform ${TOAST_FADE_MS}ms ease;
                }
                .toast.show { opacity: 1; transform: translateX(0); }
                .toast.hide { opacity: 0; transform: translateX(.75rem); }
                .toast .close {
                    /* A round badge straddling the top-left corner (half outside the
                       box), like a messaging-app dismiss bubble — not a button inside. */
                    position: absolute; top: -.7rem; left: -.7rem;
                    width: 1.85rem; height: 1.85rem; padding: 0;
                    display: flex; align-items: center; justify-content: center;
                    background: #fff; color: #334155; border: 0; border-radius: 50%;
                    box-shadow: 0 1px 5px rgba(0,0,0,.35);
                    font-size: 1.3rem; line-height: 1; cursor: pointer;
                    opacity: .95; transition: transform .12s ease;
                }
                .toast .close:hover { opacity: 1; transform: scale(1.12); }
                .toast .title { font-weight: 600; font-size: 1.2rem; }
                .toast .body { font-size: 1.05rem; opacity: .95; margin-top: .3rem; }
            </style>
            <div class="stack" role="status" aria-live="polite"></div>
        `;
        this.toasts = this.root.querySelector(".stack")!;
        this.connect();
    }

    disconnectedCallback() {
        // Intentional teardown: suppress the reconnect that the resulting close
        // event would otherwise schedule, and cancel any pending retry.
        this.closing = true;
        if (this.reconnectTimer !== undefined) clearTimeout(this.reconnectTimer);
        this.socket?.close();
    }

    attributeChangedCallback() {
        // A token/base change (e.g. host token refresh) re-points the connection,
        // but only once the element is actually mounted.
        if (this.isConnected) this.connect();
    }

    /**
     * Open the WS, re-reading `token`/`base` from the attributes on EVERY call so
     * each (re)connect carries the host's freshest JWT — a connection whose token
     * had expired re-authenticates transparently on the next attempt (slice 3).
     * Replaces any existing socket; the deliberate close it triggers is flagged so
     * it does not itself schedule a reconnect.
     */
    private connect() {
        const token = this.getAttribute("token") ?? "";
        const base = this.getAttribute("base") || window.location.origin;

        if (this.reconnectTimer !== undefined) clearTimeout(this.reconnectTimer);
        if (this.socket) {
            this.closing = true;
            this.socket.close();
        }

        this.closing = false;
        this.socket = new WebSocket(notifierWsUrl(base, token));
        this.socket.addEventListener("open", () => {
            this.backoffMs = 0; // healthy connection: forget previous backoff
        });
        this.socket.addEventListener("message", (e) => this.onMessage(e));
        this.socket.addEventListener("close", () => this.scheduleReconnect());
    }

    /**
     * After an *unexpected* close, retry with capped exponential backoff + jitter
     * so a flaky network or an expired token recovers without a page reload, while
     * a server outage is not hammered. A reconnect re-runs `connect()`, which picks
     * up the current token. No-op when the close was intentional (unmount/re-point).
     */
    private scheduleReconnect() {
        if (this.closing) return;
        const BASE_MS = 500;
        const MAX_MS = 10_000;
        this.backoffMs = Math.min(this.backoffMs ? this.backoffMs * 2 : BASE_MS, MAX_MS);
        const jitter = Math.random() * (this.backoffMs / 2);
        this.reconnectTimer = setTimeout(() => this.connect(), this.backoffMs + jitter);
    }

    private onMessage(event: MessageEvent) {
        const notification = parseNotification(String(event.data));
        if (!notification) return;

        // Suppress a scoped Notification that is not for this client's Active
        // Workshop: read the current selection on the Notification's axis from the
        // bus and let scope-filter decide. Suppressed => neither toast nor sound.
        const current = notification.scope
            ? currentSelectionId(notification.scope.axis as SelectionAxis)
            : undefined;
        if (!shouldRender(notification, current)) return;

        this.renderToast(notification);
        this.audio.play(notification.severity);
    }

    private renderToast(n: { severity: keyof typeof SEVERITY_COLOUR; title: string; body: string }) {
        const toast = document.createElement("div");
        toast.className = "toast";
        toast.style.background = SEVERITY_COLOUR[n.severity];

        // Top-left X: dismiss this toast immediately (still via the fade-out).
        const close = document.createElement("button");
        close.className = "close";
        close.type = "button";
        close.setAttribute("aria-label", "Chiudi notifica");
        close.textContent = "×"; // ×

        const title = document.createElement("div");
        title.className = "title";
        title.textContent = n.title;

        const body = document.createElement("div");
        body.className = "body";
        body.textContent = n.body;

        toast.append(close, title, body);
        this.toasts.append(toast);

        // Fade in on the next frame, after the initial opacity:0 has been applied
        // (so the transition actually runs instead of snapping to visible).
        requestAnimationFrame(() => toast.classList.add("show"));

        // Single dismissal path for both the TTL and the X: fade out, then remove
        // once the transition has finished. Guarded so the two can't double-remove.
        let dismissed = false;
        const dismiss = () => {
            if (dismissed) return;
            dismissed = true;
            clearTimeout(ttl);
            toast.classList.remove("show");
            toast.classList.add("hide");
            setTimeout(() => toast.remove(), TOAST_FADE_MS);
        };
        close.addEventListener("click", dismiss);
        const ttl = setTimeout(dismiss, TOAST_TTL_MS);
    }
}

if (!customElements.get("notification-overlay")) {
    customElements.define("notification-overlay", NotificationOverlay);
}
