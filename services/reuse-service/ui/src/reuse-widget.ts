/**
 * <reuse-widget> — the Workshop Selector, shipped by reuse-service itself as a
 * self-contained custom element.
 *
 * FRONTEND half of the full-stack Widget: the service owns both its data
 * (FastAPI /reuse/*) and its UI (this element). A framework-free Web Component,
 * so it mounts in ANY host page — the Janus monolith today, anything tomorrow.
 *
 * Contract with the host:
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 * The element calls only its OWN service's routes, always through the gateway,
 * always with the host's JWT. It never reaches the monolith.
 *
 * UI: a clickable **dropdown**. The trigger shows the current Bene; clicking it
 * opens a single-select menu. The menu is a native **popover** rendered in the
 * browser top layer and positioned with fixed coordinates from the trigger, so it
 * escapes the host widget's clipping (the dashboard card's `overflow:auto` and the
 * grid item's `transform`) and can extend beyond the widget's box — with free
 * light-dismiss + Esc. Picking a Bene publishes the Active Workshop on the
 * praim:workshop-selected bus (ADR-0003), closes the menu, and labels the trigger
 * (one Workshop at a time).
 *
 * SLICE 3 scope: the Selector owns persistence — a selection reflects the chosen
 * `poiId` into a URL query param (bookmarkable / shareable, no reload), and on load
 * the Selector restores from that param by re-using the publish path and labelling
 * the trigger. A param whose poiId is not in the list degrades cleanly. Panning the
 * GIS map is host glue (ADR-0004).
 */

import { publishActiveWorkshop } from "./active-workshop";
import { reflectSelectionInUrl, restoreActiveWorkshop, hostUrlBar } from "./selection-url";

/** One reuse-POI as returned by GET /reuse/benes. */
interface Bene {
    poiId: number;
    name: string;
    lat: number;
    lng: number;
}

const PLACEHOLDER = "Seleziona un Bene";
const MENU_ID = "reuse-menu";

const STYLES = `
    :host {
        display: block; height: 100%; font-family: inherit;
        /* Mirror the dashboard's shadcn tokens so the trigger matches its Select
           control. Light defaults; dark via prefers-color-scheme below — which tracks
           the app's default "system" theme. */
        --fg: oklch(0.145 0 0);
        --muted-fg: oklch(0.556 0 0);
        --input-border: oklch(0.922 0 0);
        --control-bg: transparent;
        --control-bg-hover: oklch(0.97 0 0);
        --menu-bg: oklch(1 0 0);
        --menu-border: oklch(0.922 0 0);
        --option-hover: oklch(0.97 0 0);
        --option-selected: oklch(0.97 0 0);
        color: var(--fg);
    }
    @media (prefers-color-scheme: dark) {
        :host {
            --fg: oklch(0.985 0 0);
            --muted-fg: oklch(0.708 0 0);
            --input-border: oklch(1 0 0 / 15%);
            --control-bg: oklch(1 0 0 / 4%);
            --control-bg-hover: oklch(1 0 0 / 8%);
            --menu-bg: oklch(0.205 0 0);
            --menu-border: oklch(1 0 0 / 10%);
            --option-hover: oklch(1 0 0 / 8%);
            --option-selected: oklch(0.279 0 0);
        }
    }
    .wrap { height: 100%; padding: 12px; box-sizing: border-box; }
    /* In the map's Lenses dock the host carries data-variant="control": drop the card
       padding so the trigger fills a 32px slot, flush like the dashboard's Select. */
    :host([data-variant="control"]) .wrap { padding: 0; }

    /* Trigger: matched to the shadcn Select trigger (size sm) — h-8, rounded-md,
       border-input, text-sm. Toggles the menu declaratively via popovertarget. */
    .select { display: flex; align-items: center; gap: 8px; width: 100%; height: 32px;
              padding: 0 12px; box-sizing: border-box; border: 1px solid var(--input-border);
              border-radius: 8px; background: var(--control-bg); color: var(--fg);
              font: inherit; font-size: 14px; font-weight: 400; text-align: left; cursor: pointer;
              box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05); }
    .select:hover:not(:disabled) { background: var(--control-bg-hover); }
    .select:disabled { cursor: default; opacity: 0.7; }
    .select .label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .select .label.placeholder { color: var(--muted-fg); }
    .chev { flex: 0 0 auto; width: 16px; height: 16px; opacity: 0.5; color: var(--fg); transition: transform 0.15s; }
    .select[aria-expanded="true"] .chev { transform: rotate(180deg); }

    /* Menu: a top-layer popover. Position (top/left/width/max-height) is set in JS
       from the trigger rect; the top layer is viewport-relative, so it is immune to
       the host card's overflow and the grid item's transform — it can spill outside
       the widget. Theme-aware to mirror the Select dropdown. */
    .menu { margin: 0; inset: auto; position: fixed; padding: 4px; box-sizing: border-box; overflow-y: auto;
            border: 1px solid var(--menu-border); border-radius: 8px; background: var(--menu-bg); color: var(--fg);
            box-shadow: 0 12px 30px rgba(0,0,0,0.3); }
    .option { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: none;
              border-radius: 6px; background: transparent; color: var(--fg); font: inherit; font-size: 14px;
              text-align: left; cursor: pointer; }
    .option:hover { background: var(--option-hover); }
    .option[aria-selected="true"] { background: var(--option-selected); color: var(--fg); }
    .option .name { flex: 1; min-width: 0; }
    .option .check { flex: 0 0 auto; color: #60a5fa; visibility: hidden; }
    .option[aria-selected="true"] .check { visibility: visible; }
`;

class ReuseWidget extends HTMLElement {
    static get observedAttributes() {
        return ["token", "base"];
    }

    private root: ShadowRoot;
    private loaded = false; // load once we have a token; refreshes don't reload
    private benesByPoiId = new Map<number, Bene>(); // lookup for the picked option's full detail

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        this.renderShell();
        // Delegated listener on the stable shadow root survives menu re-renders.
        this.root.addEventListener("click", this.onClick);
        // Reposition the popover under the trigger when it opens, and keep it there
        // while open (the trigger can move on scroll/resize). Reset state on close.
        this.root.querySelector(".menu")?.addEventListener("toggle", this.onMenuToggle);
        this.maybeLoad();
    }

    disconnectedCallback() {
        this.stopTracking();
    }

    attributeChangedCallback() {
        if (!this.isConnected) return;
        // A token arriving after mount (first login) triggers the initial load;
        // later token refreshes are no-ops because the list is already loaded.
        this.maybeLoad();
    }

    private get baseUrl(): string {
        return (this.getAttribute("base") || "").replace(/\/$/, "");
    }

    private get authToken(): string {
        return this.getAttribute("token") || "";
    }

    private async api<T>(path: string): Promise<T> {
        const res = await fetch(`${this.baseUrl}${path}`, {
            headers: this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {},
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as T;
    }

    private maybeLoad() {
        if (this.loaded || !this.authToken) return;
        this.loaded = true;
        this.setLabel("Caricamento…", true);
        this.setTriggerEnabled(false);
        void this.loadBenes();
    }

    private async loadBenes() {
        try {
            const benes = await this.api<Bene[]>("/reuse/benes");
            this.renderBenes(benes);
        } catch {
            this.loaded = false; // let a later token/attribute change retry
            this.setLabel("Impossibile caricare i Bene.", true);
            this.setTriggerEnabled(false);
        }
    }

    private renderShell() {
        this.root.innerHTML = `
            <style>${STYLES}</style>
            <div class="wrap">
                <button type="button" class="select" popovertarget="${MENU_ID}"
                        aria-haspopup="listbox" aria-expanded="false" disabled>
                    <span class="label placeholder">${
                        this.authToken ? "Caricamento…" : "In attesa di autenticazione…"
                    }</span>
                    <span class="chev" aria-hidden="true">▾</span>
                </button>
                <div id="${MENU_ID}" class="menu" popover="auto" role="listbox"></div>
            </div>
        `;
    }

    // The dropdown options: one selectable row per Bene (single-select listbox).
    private renderBenes(benes: Bene[]) {
        this.benesByPoiId = new Map(benes.map((b) => [b.poiId, b]));
        if (benes.length === 0) {
            this.setLabel("Nessun Bene", true);
            this.setTriggerEnabled(false);
            return;
        }
        this.setMenu(
            benes
                .map(
                    (b) =>
                        `<button type="button" class="option" role="option" data-poi-id="${b.poiId}" aria-selected="false"><span class="name">${escapeHtml(
                            b.name,
                        )}</span><span class="check" aria-hidden="true">✓</span></button>`,
                )
                .join(""),
        );
        this.setTriggerEnabled(true);

        // Restore a selection carried by the URL (reload / shared link): re-publish it
        // through the bus so already-mounted sensitive widgets converge, then label the
        // trigger and mark its option. Otherwise show the neutral placeholder.
        const restored = restoreActiveWorkshop(benes, hostUrlBar);
        if (restored) this.markSelected(restored.poiId);
        else this.setLabel(PLACEHOLDER, true);
    }

    private onClick = (e: Event) => {
        // The trigger toggles the popover declaratively (popovertarget); we only
        // handle option picks here.
        const option = (e.target as HTMLElement).closest<HTMLElement>(".option");
        if (option) this.select(Number(option.dataset.poiId));
    };

    // Picking a Bene publishes it as the Active Workshop (ADR-0003), labels the
    // trigger, marks its option, and closes the menu — exactly one at a time.
    private select(poiId: number) {
        const bene = this.benesByPoiId.get(poiId);
        if (!bene) return;
        this.markSelected(poiId);
        publishActiveWorkshop(bene);
        // Reflect the choice into the URL so the dashboard is bookmarkable/shareable.
        reflectSelectionInUrl(bene.poiId, hostUrlBar);
        this.root.querySelector<HTMLElement & { hidePopover(): void }>(".menu")?.hidePopover();
    }

    // Label the trigger with the chosen Bene and move the single aria-selected mark.
    private markSelected(poiId: number) {
        const bene = this.benesByPoiId.get(poiId);
        if (bene) this.setLabel(bene.name, false);
        this.root
            .querySelectorAll<HTMLElement>('.option[aria-selected="true"]')
            .forEach((el) => el.setAttribute("aria-selected", "false"));
        this.root
            .querySelector<HTMLElement>(`.option[data-poi-id="${poiId}"]`)
            ?.setAttribute("aria-selected", "true");
    }

    // --- popover positioning (top layer, fixed to the viewport) ----------------

    private onMenuToggle = (e: Event) => {
        const open = (e as Event & { newState?: string }).newState === "open";
        this.root.querySelector(".select")?.setAttribute("aria-expanded", String(open));
        if (open) {
            this.positionMenu();
            window.addEventListener("scroll", this.positionMenu, true);
            window.addEventListener("resize", this.positionMenu);
        } else {
            this.stopTracking();
        }
    };

    private stopTracking() {
        window.removeEventListener("scroll", this.positionMenu, true);
        window.removeEventListener("resize", this.positionMenu);
    }

    // Place the menu directly under the trigger (or above it when there is more room
    // there), in viewport coordinates. Bounded so a long list scrolls instead of
    // running off-screen.
    private positionMenu = () => {
        const trigger = this.root.querySelector<HTMLElement>(".select");
        const menu = this.root.querySelector<HTMLElement>(".menu");
        if (!trigger || !menu) return;
        const r = trigger.getBoundingClientRect();
        const gap = 4;
        const below = window.innerHeight - r.bottom - gap;
        const above = r.top - gap;
        const openUp = below < 180 && above > below;
        menu.style.left = `${Math.round(r.left)}px`;
        menu.style.width = `${Math.round(r.width)}px`;
        menu.style.maxHeight = `${Math.round(Math.min(360, Math.max(120, openUp ? above : below)))}px`;
        if (openUp) {
            menu.style.top = "auto";
            menu.style.bottom = `${Math.round(window.innerHeight - r.top + gap)}px`;
        } else {
            menu.style.bottom = "auto";
            menu.style.top = `${Math.round(r.bottom + gap)}px`;
        }
    };

    // --- small DOM helpers -----------------------------------------------------

    private setLabel(text: string, placeholder: boolean) {
        const label = this.root.querySelector<HTMLElement>(".select .label");
        if (!label) return;
        label.textContent = text;
        label.classList.toggle("placeholder", placeholder);
    }

    private setTriggerEnabled(enabled: boolean) {
        const trigger = this.root.querySelector<HTMLButtonElement>(".select");
        if (trigger) trigger.disabled = !enabled;
    }

    private setMenu(html: string) {
        const menu = this.root.querySelector<HTMLElement>(".menu");
        if (menu) menu.innerHTML = html;
    }
}

function escapeHtml(s: string): string {
    return s.replace(
        /[&<>"']/g,
        (c) =>
            ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
    );
}

if (!customElements.get("reuse-widget")) {
    customElements.define("reuse-widget", ReuseWidget);
}
