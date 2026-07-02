/**
 * <likert-widget> — the Scala Likert dashboard widget, shipped by likert-service
 * itself as a self-contained custom element.
 *
 * The FRONTEND half of the full-stack Widget: the service owns both its data
 * (FastAPI /likert/gradimento) and its UI (this element). A standard Web Component
 * with no framework, it mounts in ANY host page.
 *
 * It reacts to TWO inputs at once (CONTEXT.md): the Active Vocazione (consumed off
 * the generalized selection bus, ADR-0005 — `praim:selection:vocazione`, value
 * `{ id, label } | null`) and the clicked comune (the host-set `lat`/`lng` every
 * Widget receives). Only with BOTH present does it call the data route and render
 * the gauge — a red→green bar with a needle at the Gradimento, an emoji, the star
 * average and a one-word label (scale.ts). Missing either input shows the matching
 * prompt. It IGNORES the Active Workshop (it is not a sensitive/Bene widget).
 *
 * Contract with the host (mirrors the sibling widgets):
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 */

import { readSelection, subscribeSelection } from "./selection-bus";
import { toScale } from "./scale";

/** The Active Vocazione value carried on the `vocazione` selection axis. */
interface Vocazione {
    id: string;
    label: string;
}

/** The /likert/gradimento payload (PRD API contract). */
interface Gradimento {
    comune: { region_id: number; name: string };
    vocazione: string;
    status: "ok" | "insufficient" | "no_competitors";
    gradimento: number | null;
    total_reviews: number;
    n_competitors: number;
    n_rated: number;
    low_confidence: boolean;
    updated_at: string | null;
    breakdown: { poi_id: number; name: string; categoria: string; rating: number; n_ratings: number }[];
}

const STYLES = `
    :host { display: block; position: relative; height: 100%; font-family: system-ui, sans-serif; color: #f9fafb; }
    .wrap { display: flex; flex-direction: column; gap: 10px; height: 100%; padding: 12px; box-sizing: border-box; }
    header { text-align: center; }
    h2 { font-size: 14px; font-weight: 700; margin: 0; color: #ffffff; letter-spacing: 0.03em; text-transform: uppercase; }
    .sub { font-size: 11px; color: #cbd5e1; }
    .body { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 0; gap: 8px; }
    .state { color: #cbd5e1; font-size: 13px; text-align: center; padding: 0 12px; box-sizing: border-box; }
    .error { color: #fca5a5; }

    /* The gauge: a red→yellow→green bar with a needle at the Gradimento. */
    .gauge { width: 100%; max-width: 280px; display: flex; flex-direction: column; align-items: center; gap: 8px; }
    .emoji { font-size: 34px; line-height: 1; }
    .bar { position: relative; width: 100%; height: 14px; border-radius: 999px;
           background: linear-gradient(to right, hsl(0,70%,45%), hsl(60,70%,45%), hsl(120,70%,45%)); }
    .needle { position: absolute; top: -4px; bottom: -4px; width: 3px; border-radius: 2px;
              background: #ffffff; box-shadow: 0 0 0 1px rgba(0,0,0,0.4); transform: translateX(-50%); }
    .readout { display: flex; align-items: baseline; gap: 8px; }
    .stars { font-size: 18px; font-weight: 800; color: #ffffff; font-variant-numeric: tabular-nums; }
    .label { font-size: 13px; color: #e2e8f0; }
    .faded { opacity: 0.55; }
    .note { font-size: 11px; color: #fbbf24; }
    .gauge.clickable { cursor: pointer; }
    .gauge.clickable:focus-visible { outline: 2px solid #93c5fd; outline-offset: 4px; border-radius: 8px; }
    .hint { font-size: 10px; color: #94a3b8; }
`;

// The detail modal renders in its OWN element portaled to document.body (see
// openModal): a dashboard grid cell carries a CSS `transform`, which would make a
// `position: fixed` child resolve against the cell, not the viewport — so the modal
// must live outside the widget's shadow tree to cover the full page. These styles
// ship in that portal's own shadow root, fully self-contained (PRD US 14–19).
const MODAL_STYLES = `
    :host { all: initial; }
    .backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.65); z-index: 2147483000;
                display: flex; align-items: center; justify-content: center; padding: 24px; box-sizing: border-box;
                font-family: system-ui, sans-serif; }
    .modal { width: 100%; max-width: 560px; max-height: 85vh; overflow: auto; outline: none; color: #f9fafb;
             background: #111827; border: 1px solid rgba(255,255,255,0.15); border-radius: 12px;
             padding: 20px 22px; box-sizing: border-box; box-shadow: 0 24px 60px rgba(0,0,0,0.5); }
    .modal h3 { display: flex; justify-content: space-between; align-items: center; margin: 0 0 10px;
                font-size: 15px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 0.03em; }
    .modal .close { cursor: pointer; border: none; background: transparent; color: #cbd5e1; font-size: 24px; line-height: 1; padding: 0 4px; }
    .caption { font-size: 13px; color: #cbd5e1; margin: 0 0 14px; }
    .rollup { display: grid; grid-template-columns: 1fr auto; gap: 6px 14px; font-size: 14px; margin-bottom: 16px; }
    .rollup .k { color: #cbd5e1; }
    .rollup .v { text-align: right; font-weight: 700; color: #fff; font-variant-numeric: tabular-nums; }
    .modal table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .modal th { text-align: left; color: #94a3b8; font-weight: 600; padding: 6px 6px; position: sticky; top: 0;
                background: #111827; border-bottom: 1px solid rgba(255,255,255,0.15); }
    .modal td { padding: 8px 6px; border-bottom: 1px solid rgba(255,255,255,0.08); color: #f9fafb; vertical-align: top; }
    .modal td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .caveat { font-size: 12px; color: #fbbf24; margin: 12px 0 0; }
    .updated { font-size: 12px; color: #94a3b8; margin: 10px 0 0; }
`;

class LikertWidget extends HTMLElement {
    static get observedAttributes() {
        return ["token", "base", "lat", "lng"];
    }

    private root: ShadowRoot;
    private vocazione: Vocazione | null = null;
    // The resolved comune name, shown in the header sub-line so the user sees which
    // territory the Gradimento is for; null until a payload resolves a comune.
    private comuneName: string | null = null;
    // The last resolved `ok` payload — the source the detail modal renders from.
    // Null whenever there is no gauge to click (prompt/empty/insufficient state).
    private data: Gradimento | null = null;
    // The full-page modal lives in its OWN element appended to document.body (a
    // portal, so it escapes the grid cell's transform); null while closed.
    private modalHost: HTMLElement | null = null;
    private unsubscribe?: () => void;

    // Document-level Escape close (the portal is outside this element's shadow tree,
    // so the widget's own keydown listener can't see it). Bound once for add/remove.
    private readonly onKeydown = (e: KeyboardEvent) => {
        if (e.key === "Escape") this.closeModal();
    };

    // The last "lat,lng,vocazione" we resolved, so the two sequential lat/lng
    // attribute writes (and a no-op token refresh) coalesce into one fetch.
    private lastKey: string | null = null;
    private fetchScheduled = false;

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        // Converge on the retained Active Vocazione at mount (late mount / HMR),
        // then track changes. `null` = "Tutte le vocazioni" → empty state.
        this.vocazione = (readSelection<Vocazione>("vocazione") ?? null);
        this.unsubscribe = subscribeSelection<Vocazione>("vocazione", (value) => {
            this.vocazione = value;
            this.scheduleFetch(true);
        });
        // Open the detail modal when the gauge is clicked (or Enter/Space on it),
        // close it on the ✕ / backdrop / Escape — the sibling widgets' convention.
        this.root.addEventListener("click", (e) => this.onClick(e));
        this.root.addEventListener("keydown", (e) => {
            const ke = e as KeyboardEvent;
            if (ke.key === "Escape") {
                this.closeModal();
                return;
            }
            if ((ke.key === "Enter" || ke.key === " ") && (e.target as HTMLElement).closest("[data-open]")) {
                e.preventDefault();
                this.openModal();
            }
        });
        this.renderShell();
        this.scheduleFetch();
    }

    disconnectedCallback() {
        this.unsubscribe?.();
        this.unsubscribe = undefined;
        // Drop the portaled modal if the widget unmounts while it is open.
        this.closeModal();
    }

    attributeChangedCallback(name: string) {
        if (!this.isConnected) return;
        if (name === "token" || name === "lat" || name === "lng") this.scheduleFetch();
    }

    // NOTE: deliberately NOT named `base`/`token` — React sets a custom element's
    // matching *property* when one exists, and a getter-only property would throw
    // on assignment; different names keep React setting the attributes we observe.
    private get baseUrl(): string {
        return (this.getAttribute("base") || "").replace(/\/$/, "");
    }

    private get authToken(): string {
        return this.getAttribute("token") || "";
    }

    /** Coalesce the host's lat/lng writes and the bus change into a single fetch on
     *  the next microtask. `force` re-fetches even if the point is unchanged (the
     *  Vocazione changed for the same comune). */
    private scheduleFetch(force = false) {
        if (this.fetchScheduled) return;
        this.fetchScheduled = true;
        queueMicrotask(() => {
            this.fetchScheduled = false;
            this.resolve(force);
        });
    }

    private resolve(force: boolean) {
        const lat = this.getAttribute("lat");
        const lng = this.getAttribute("lng");
        // Leaving the resolved view (prompt/empty state) drops the comune name from
        // the header; the fetch path re-sets it from the payload. A fresh selection
        // also closes any open detail modal and drops its stale source.
        this.comuneName = null;
        this.data = null;
        this.closeModal();
        // Both inputs are required; either missing shows the matching prompt and
        // does NOT call the route.
        if (!this.vocazione) {
            this.lastKey = null;
            this.renderState("Seleziona una vocazione.");
            return;
        }
        if (!lat || !lng) {
            this.lastKey = null;
            this.renderState("Clicca un comune sulla mappa.");
            return;
        }
        if (!this.authToken) return; // wait for the host token; a later change re-arms

        const key = `${lat},${lng},${this.vocazione.id}`;
        if (!force && key === this.lastKey) return;
        this.lastKey = key;
        void this.load(lat, lng, this.vocazione.id);
    }

    private async load(lat: string, lng: string, vocazione: string) {
        this.comuneName = null;
        this.renderState("Caricamento…");
        try {
            const res = await fetch(
                `${this.baseUrl}/likert/gradimento?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(
                    lng,
                )}&vocazione=${encodeURIComponent(vocazione)}`,
                { headers: this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {} },
            );
            // A click outside every comune (e.g. the sea) is a 404 — a graceful
            // empty state, NOT a broken card: there is simply no comune here.
            if (res.status === 404) {
                this.renderState("Nessun comune qui. Clicca sulla terraferma.");
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            this.renderGradimento((await res.json()) as Gradimento);
        } catch {
            this.renderState("Impossibile caricare il gradimento.", true);
        }
    }

    // --- rendering -----------------------------------------------------------

    private headerText(): string {
        return this.vocazione?.label ?? "Scala Likert";
    }

    private renderShell() {
        this.paint(`<div class="state">Seleziona una vocazione e clicca un comune.</div>`);
    }

    private renderState(message: string, isError = false) {
        this.paint(`<div class="state${isError ? " error" : ""}">${escapeHtml(message)}</div>`);
    }

    private renderGradimento(data: Gradimento) {
        // The real comune resolved from the click — shown in the header sub-line.
        this.comuneName = data.comune?.name ?? null;
        // No gauge ⇒ nothing to drill into: drop any modal source.
        this.data = null;
        if (data.status === "no_competitors") {
            this.renderState("Nessun concorrente di mercato per questa vocazione.");
            return;
        }
        if (data.status !== "ok" || data.gradimento == null) {
            this.renderState("Dati insufficienti per questo comune.");
            return;
        }
        // Keep the payload so the detail modal can render the breakdown on click.
        this.data = data;
        const scale = toScale(data.gradimento, data.total_reviews);
        const faded = scale.lowConfidence ? " faded" : "";
        const note = scale.lowConfidence ? `<div class="note">pochi dati</div>` : "";
        this.paint(`
            <div class="gauge clickable${faded}" data-open role="button" tabindex="0" aria-label="Mostra i dettagli del gradimento">
                <div class="emoji">${scale.emoji}</div>
                <div class="bar">
                    <div class="needle" style="left:${(scale.position * 100).toFixed(1)}%; background:${scale.color}"></div>
                </div>
                <div class="readout">
                    <span class="stars">${data.gradimento.toFixed(1)} ★</span>
                    <span class="label">${escapeHtml(scale.label)}</span>
                </div>
            </div>
            ${note}
            <div class="hint">Clicca per i dettagli</div>`);
    }

    private paint(body: string) {
        this.root.innerHTML = `
            <style>${STYLES}</style>
            <div class="wrap">
                <header>
                    <h2>${escapeHtml(this.headerText())}</h2>
                    <div class="sub">${escapeHtml(this.comuneName ?? "Gradimento di mercato")}</div>
                </header>
                <div class="body">${body}</div>
            </div>`;
    }

    // --- detail modal (PRD US 14–19) -----------------------------------------

    private onClick(e: Event) {
        // A click anywhere on the gauge opens the full-page modal.
        if ((e.target as HTMLElement).closest("[data-open]")) this.openModal();
    }

    // Close on the ✕ button or a click on the dimmed backdrop, inside the portal's
    // own shadow tree (its events don't reach the widget's shadow root).
    private onModalClick(e: Event) {
        const target = e.target as HTMLElement;
        if (target.closest("[data-close]") || target.classList.contains("backdrop")) this.closeModal();
    }

    /** Open the modal listing the competitors and the rollup behind the Gradimento,
     *  so the conclusion is auditable. Rendered full-page in a portal appended to
     *  document.body. No-op unless an `ok` payload is in hand. */
    private openModal() {
        const data = this.data;
        if (!data || data.status !== "ok" || data.gradimento == null) return;
        this.closeModal();

        const scale = toScale(data.gradimento, data.total_reviews);
        // Each contributing competitor: name, categoria, its ★ average and review
        // count (the payload is already ordered desc by review count).
        const rows = data.breakdown
            .map(
                (b) => `
                <tr>
                    <td>${escapeHtml(b.name)}</td>
                    <td>${escapeHtml(b.categoria ?? "")}</td>
                    <td class="num">${b.rating.toFixed(1)} ★</td>
                    <td class="num">${b.n_ratings}</td>
                </tr>`,
            )
            .join("");
        // "aggiornato il …" — freshness of the contributing ratings.
        const updated = data.updated_at
            ? new Date(data.updated_at).toLocaleDateString("it-IT", { day: "numeric", month: "long", year: "numeric" })
            : "—";
        // The low-confidence caveat travels with the detail (US 18).
        const caveat = data.low_confidence
            ? `<p class="caveat">Stima a bassa confidenza: pochi dati (${data.total_reviews} recensioni).</p>`
            : "";

        // Portal host appended to document.body so `position: fixed` covers the whole
        // viewport regardless of the grid cell's transform. Its own shadow root keeps
        // the modal styles from leaking into — or being overridden by — the host page.
        const host = document.createElement("div");
        const shadow = host.attachShadow({ mode: "open" });
        shadow.innerHTML = `
            <style>${MODAL_STYLES}</style>
            <div class="backdrop" tabindex="-1">
                <div class="modal" role="dialog" aria-modal="true" aria-label="Dettaglio gradimento">
                    <h3>Dettaglio gradimento<button class="close" type="button" data-close aria-label="Chiudi">×</button></h3>
                    <p class="caption">Media pesata delle valutazioni online dei <strong>concorrenti di mercato</strong>${
                        data.comune?.name ? ` in ${escapeHtml(data.comune.name)}` : ""
                    } — non della vocazione stessa.</p>
                    <div class="rollup">
                        <span class="k">Gradimento</span><span class="v">${data.gradimento.toFixed(1)} ★ · ${escapeHtml(scale.label)}</span>
                        <span class="k">Concorrenti trovati</span><span class="v">${data.n_competitors}</span>
                        <span class="k">Con valutazione</span><span class="v">${data.n_rated}</span>
                        <span class="k">Recensioni totali</span><span class="v">${data.total_reviews}</span>
                    </div>
                    ${
                        rows
                            ? `<table><thead><tr><th>Concorrente</th><th>Categoria</th><th class="num">Media</th><th class="num">Rec.</th></tr></thead><tbody>${rows}</tbody></table>`
                            : ""
                    }
                    ${caveat}
                    <p class="updated">Aggiornato il ${updated}</p>
                </div>
            </div>`;
        shadow.addEventListener("click", (e) => this.onModalClick(e));
        document.body.appendChild(host);
        this.modalHost = host;
        document.addEventListener("keydown", this.onKeydown);
        (shadow.querySelector(".backdrop") as HTMLElement | null)?.focus();
    }

    private closeModal() {
        if (!this.modalHost) return;
        document.removeEventListener("keydown", this.onKeydown);
        this.modalHost.remove();
        this.modalHost = null;
    }
}

function escapeHtml(s: string): string {
    return s.replace(
        /[&<>"']/g,
        (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] as string,
    );
}

if (!customElements.get("likert-widget")) {
    customElements.define("likert-widget", LikertWidget);
}
