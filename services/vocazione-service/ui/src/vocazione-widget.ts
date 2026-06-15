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
    :host { display: block; height: 100%; font-family: system-ui, sans-serif; color: #f9fafb; }
    .wrap { height: 100%; padding: 12px; box-sizing: border-box; }

    /* Trigger: shows the current Vocazione (or a placeholder) and toggles the menu
       declaratively via popovertarget — the browser handles invoker toggling. */
    .select { display: flex; align-items: center; gap: 10px; width: 100%; padding: 9px 12px;
              border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; background: rgba(255,255,255,0.05);
              color: #fff; font: inherit; font-size: 13px; font-weight: 600; text-align: left; cursor: pointer; }
    .select:hover { background: rgba(255,255,255,0.09); }
    .select .label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .select .label.placeholder { color: #cbd5e1; font-weight: 500; }
    .chev { flex: 0 0 auto; color: #cbd5e1; transition: transform 0.15s; }
    .select[aria-expanded="true"] .chev { transform: rotate(180deg); }

    /* Menu: a top-layer popover. Position (top/left/width/max-height) is set in JS
       from the trigger rect; the top layer is viewport-relative, so it is immune to
       the host card's overflow and the grid item's transform — it can spill outside
       the widget. UA gives display + light-dismiss; we just reset its box. */
    .menu { margin: 0; inset: auto; position: fixed; padding: 4px; box-sizing: border-box; overflow-y: auto;
            border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; background: #111827; color: #f9fafb;
            box-shadow: 0 12px 30px rgba(0,0,0,0.5); }
    .option { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: none;
              border-radius: 6px; background: transparent; color: #f9fafb; font: inherit; font-size: 13px;
              text-align: left; cursor: pointer; }
    .option:hover { background: rgba(255,255,255,0.08); }
    .option[aria-selected="true"] { background: rgba(96,165,250,0.18); color: #fff; }
    .option .name { flex: 1; min-width: 0; }
    .option .check { flex: 0 0 auto; color: #60a5fa; visibility: hidden; }
    .option[aria-selected="true"] .check { visibility: visible; }
    /* The clear entry sits apart from the 16, with a hairline divider below it. */
    .option.clear { color: #cbd5e1; border-bottom: 1px solid rgba(255,255,255,0.10); border-radius: 0; margin-bottom: 4px; }
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
