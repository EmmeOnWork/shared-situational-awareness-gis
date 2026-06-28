/**
 * <vocazione-widget> — the Vocazione Selector, shipped by vocazione-service
 * itself as a self-contained custom element.
 *
 * FRONTEND half of a deliberately client-only full-stack Widget: the service
 * serves this bundle but owns NO data route. A framework-free Web Component, so
 * it mounts in ANY host page — the Janus monolith today, anything tomorrow.
 *
 * Contract with the host (same as the sibling Widgets, so the generic
 * RemoteWidget seam mounts it identically):
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 * Both attributes are accepted **harmlessly**: this Widget fetches nothing and
 * calls no data route, so the token is never used and `base` resolves no request.
 * It is therefore usable immediately, before any token arrives.
 *
 * UI: a clickable single-select **dropdown** of the 16 Vocazioni plus a "Tutte le
 * vocazioni" clear entry. The menu is a native **popover** rendered in the browser
 * top layer and positioned with fixed coordinates from the trigger, so it escapes
 * the host card's clipping (`overflow:auto` + the grid item's `transform`) and can
 * open above when there is more room — reusing the reuse-widget approach. Picking a
 * Vocazione publishes it as the Active Vocazione on the generalized selection bus
 * (`praim:selection:vocazione`, ADR-0005) and labels the trigger; picking "Tutte"
 * publishes `null` (cleared / show-all) and resets the trigger. One — or none — at a
 * time; the trigger always reflects the current choice.
 *
 * The chosen slug is also reflected into a `?vocazione=<slug>` URL param (and
 * restored at mount) so a focused dashboard is bookmarkable/shareable — see
 * `vocazione-url` (Slice 3, ADR-0005).
 */

import { VOCAZIONI, findVocazione, type Vocazione } from "./vocazioni";
import { publishSelection } from "./selection-bus";
import { reflectSelectionInUrl, restoreVocazione, hostUrlBar } from "./vocazione-url";

const PLACEHOLDER = "Seleziona una Vocazione";
const CLEAR_LABEL = "Tutte le vocazioni";
const CLEAR_ID = ""; // the clear entry's data-id: empty slug === "show all"
const MENU_ID = "vocazione-menu";

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
    .select:hover { background: var(--control-bg-hover); }
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
    /* The clear entry sits apart from the 16, with a hairline divider below it. */
    .option.clear { color: var(--muted-fg); border-bottom: 1px solid var(--menu-border); border-radius: 0; margin-bottom: 4px; }
`;

class VocazioneWidget extends HTMLElement {
    static get observedAttributes() {
        // Observed so the host can set them harmlessly; we never act on them (this
        // Widget fetches nothing and calls no data route).
        return ["token", "base"];
    }

    private root: ShadowRoot;

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        this.render();
        // Delegated listener on the stable shadow root survives any re-render.
        this.root.addEventListener("click", this.onClick);
        // Reposition the popover under (or above) the trigger when it opens, and keep
        // it there while open (the trigger can move on scroll/resize).
        this.root.querySelector(".menu")?.addEventListener("toggle", this.onMenuToggle);

        // Restore a selection carried by the URL (reload / shared link): re-publish it
        // through the bus so already-mounted consumers converge, then label the trigger
        // and mark its option. An absent/stale slug degrades to the neutral placeholder.
        const restored = restoreVocazione(hostUrlBar);
        if (restored) this.markSelected(restored);
    }

    disconnectedCallback() {
        this.stopTracking();
    }

    attributeChangedCallback() {
        // Intentionally a no-op: token/base carry no behaviour (nothing is fetched).
    }

    private render() {
        // The clear entry first, then the 16 Vocazioni — all static (no data load).
        const clearOption = `<button type="button" class="option clear" role="option" data-id="${CLEAR_ID}" aria-selected="false"><span class="name">${CLEAR_LABEL}</span><span class="check" aria-hidden="true">✓</span></button>`;
        const options = VOCAZIONI.map(
            (v) =>
                `<button type="button" class="option" role="option" data-id="${v.id}" aria-selected="false"><span class="name">${escapeHtml(
                    v.label,
                )}</span><span class="check" aria-hidden="true">✓</span></button>`,
        ).join("");
        this.root.innerHTML = `
            <style>${STYLES}</style>
            <div class="wrap">
                <button type="button" class="select" popovertarget="${MENU_ID}"
                        aria-haspopup="listbox" aria-expanded="false">
                    <span class="label placeholder">${PLACEHOLDER}</span>
                    <span class="chev" aria-hidden="true">▾</span>
                </button>
                <div id="${MENU_ID}" class="menu" popover="auto" role="listbox">${clearOption}${options}</div>
            </div>
        `;
    }

    private onClick = (e: Event) => {
        // The trigger toggles the popover declaratively (popovertarget); we only
        // handle option picks here.
        const option = (e.target as HTMLElement).closest<HTMLElement>(".option");
        if (option) this.select(option.dataset.id ?? CLEAR_ID);
    };

    // Picking an option publishes the Active Vocazione (ADR-0005) and closes the menu.
    // An empty id is the "Tutte le vocazioni" clear → publish `null` (show-all).
    private select(id: string) {
        if (id === CLEAR_ID) {
            publishSelection<Vocazione>("vocazione", null);
            reflectSelectionInUrl(null, hostUrlBar); // "Tutte" → drop the param entirely
            this.setLabel(PLACEHOLDER, true);
            this.clearMarks();
        } else {
            const vocazione = findVocazione(id);
            if (!vocazione) return;
            publishSelection<Vocazione>("vocazione", vocazione);
            reflectSelectionInUrl(vocazione.id, hostUrlBar); // bookmarkable/shareable
            this.markSelected(vocazione);
        }
        this.root.querySelector<HTMLElement & { hidePopover(): void }>(".menu")?.hidePopover();
    }

    // Label the trigger with the chosen Vocazione and move the single selected mark.
    private markSelected(vocazione: Vocazione) {
        this.setLabel(vocazione.label, false);
        this.clearMarks();
        this.root
            .querySelector<HTMLElement>(`.option[data-id="${vocazione.id}"]`)
            ?.setAttribute("aria-selected", "true");
    }

    private clearMarks() {
        this.root
            .querySelectorAll<HTMLElement>('.option[aria-selected="true"]')
            .forEach((el) => el.setAttribute("aria-selected", "false"));
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
    // there), in viewport coordinates. Bounded so the list scrolls instead of running
    // off-screen.
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

    // --- small DOM helper ------------------------------------------------------

    private setLabel(text: string, placeholder: boolean) {
        const label = this.root.querySelector<HTMLElement>(".select .label");
        if (!label) return;
        label.textContent = text;
        label.classList.toggle("placeholder", placeholder);
    }
}

function escapeHtml(s: string): string {
    return s.replace(
        /[&<>"']/g,
        (c) =>
            ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
    );
}

if (!customElements.get("vocazione-widget")) {
    customElements.define("vocazione-widget", VocazioneWidget);
}
