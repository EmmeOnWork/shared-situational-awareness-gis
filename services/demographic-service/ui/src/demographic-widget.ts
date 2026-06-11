/**
 * <demographic-widget> — the demographic dashboard widget, shipped by the
 * demographic-service itself as a self-contained custom element.
 *
 * This is the FRONTEND half of the full-stack Widget: the service owns both its
 * data (FastAPI /demographics/*) and its UI (this element). It is a standard Web
 * Component with no framework, so it mounts in ANY host page — the Janus monolith
 * today, anything tomorrow — which is exactly what makes the Widget reusable and
 * independent of the monolith (the strangler-fig end state).
 *
 * Contract with the host (see docs/architecture/widget-microservice-fullstack.md):
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 * The element calls only its OWN service's routes, always through the gateway,
 * always with the host's JWT. It never reaches the monolith.
 */

/** The canonical DataResponse contract, as returned by /demographics/*. */
interface DataResponse {
    label: string;
    data: Record<string, number | null>;
    metadata?: {
        territory_name?: string;
        level?: string;
        population_unit?: string;
        population_reference_date?: string;
        rates_reference_year?: number;
        quality_flags?: Record<string, string>;
    };
}

// How each value is read for display. ISTAT ships population counts in THOUSANDS
// (so Avellino's raw 393.1 means 393.100 residents — not "393,1 people"), age
// groups as percentage shares, and migration balances as rates per 1000.
type IndicatorKind = "population" | "share" | "rate";

// The nine indicators grouped into the three categories the widget shows as
// tiles. Each tile shows one headline indicator; clicking it opens a modal with
// all three of that category. `icon` is an emoji (the lightest possible glyph —
// no asset, no request); the age tile uses a CSS "65+" badge instead.
interface Category {
    key: string;
    label: string; // tile caption + modal title
    icon: string; // emoji, or "" when `badge` is used
    badge?: string; // CSS-circle text shown instead of an emoji
    kind: IndicatorKind; // how every value in this category is formatted
    headline: string; // indicator key shown on the tile
    indicators: { key: string; label: string }[]; // all three, for the modal
}

const CATEGORIES: Category[] = [
    {
        key: "population",
        label: "Popolazione",
        icon: "👤",
        kind: "population",
        headline: "pop_total",
        indicators: [
            { key: "pop_total", label: "Totale" },
            { key: "pop_italian", label: "Italiana" },
            { key: "pop_foreign", label: "Straniera" },
        ],
    },
    {
        key: "age",
        label: "Quota 65+",
        icon: "",
        badge: "65+",
        kind: "share",
        headline: "age_share_65_plus",
        indicators: [
            { key: "age_share_0_14", label: "0–14 anni" },
            { key: "age_share_15_64", label: "15–64 anni" },
            { key: "age_share_65_plus", label: "65+ anni" },
        ],
    },
    {
        key: "migration",
        label: "Saldo migratorio",
        icon: "✈️",
        kind: "rate",
        headline: "mig_rate_total",
        indicators: [
            { key: "mig_rate_internal", label: "Interno" },
            { key: "mig_rate_foreign", label: "Estero" },
            { key: "mig_rate_total", label: "Totale" },
        ],
    },
];

const QUALITY_LABELS: Record<string, string> = {
    S: "stima",
    P: "provvisorio",
};

// Population is scaled from thousands to whole residents so it reads as people
// ("393.100"); shares get a percent sign, migration balances a per-mille sign.
function formatValue(raw: number | null, kind: IndicatorKind): string {
    if (raw == null) return "—";
    if (kind === "population") return Math.round(raw * 1000).toLocaleString("it-IT");
    const num = raw.toLocaleString("it-IT", { maximumFractionDigits: 1 });
    return kind === "share" ? `${num} %` : `${num} ‰`;
}

const STYLES = `
    :host { display: block; position: relative; height: 100%; font-family: system-ui, sans-serif; color: #f9fafb; }
    .wrap { display: flex; flex-direction: column; gap: 12px; height: 100%; padding: 12px; box-sizing: border-box; }
    header { text-align: center; }
    h2 { font-size: 15px; font-weight: 700; margin: 0; color: #ffffff; letter-spacing: 0.03em; text-transform: uppercase; }
    .body { flex: 1; display: flex; min-height: 0; }

    /* The three category tiles */
    .tiles { display: flex; gap: 10px; width: 100%; align-items: stretch; }
    .tile { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
            padding: 10px 6px; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 10px;
            background: rgba(255, 255, 255, 0.03); color: inherit; font: inherit; cursor: pointer;
            transition: background 0.15s, border-color 0.15s; }
    .tile:hover { background: rgba(255, 255, 255, 0.08); border-color: rgba(255, 255, 255, 0.35); }
    .tile:focus-visible { outline: 2px solid #93c5fd; outline-offset: 2px; }
    /* Force the colour emoji to a solid white silhouette (white-on-black). */
    .tile .icon { font-size: 30px; line-height: 1; filter: grayscale(1) brightness(0) invert(1); }
    .tile .badge { width: 44px; height: 44px; border-radius: 9999px; border: 2px solid #f9fafb;
                   display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; }
    .tile .cat { font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; color: #cbd5e1; text-align: center; }
    .tile .value { font-size: 16px; font-weight: 700; color: #ffffff; font-variant-numeric: tabular-nums; }

    .state { display: flex; align-items: center; justify-content: center; width: 100%; color: #cbd5e1; font-size: 13px; text-align: center; padding: 0 12px; box-sizing: border-box; }
    .error { color: #fca5a5; }

    /* Modal: all three indicators of the clicked category */
    .backdrop { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.6); display: flex;
                align-items: center; justify-content: center; padding: 16px; box-sizing: border-box; }
    .modal { width: 100%; max-width: 320px; background: #111827; border: 1px solid rgba(255, 255, 255, 0.15);
             border-radius: 12px; padding: 14px 16px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5); }
    .modal h3 { margin: 0 0 10px; font-size: 13px; font-weight: 700; color: #ffffff; text-transform: uppercase;
                letter-spacing: 0.03em; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .modal .close { cursor: pointer; border: none; background: transparent; color: #cbd5e1; font-size: 20px; line-height: 1; padding: 0 4px; }
    .modal table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .modal td { padding: 7px 4px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); color: #f9fafb; }
    .modal td.value { text-align: right; font-variant-numeric: tabular-nums; font-weight: 700; color: #ffffff; }
    .flag { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 9999px; font-size: 10px; background: #eef2ff; color: #4338ca; vertical-align: middle; }
    .meta { font-size: 11px; color: #cbd5e1; margin: 10px 0 0; }
`;

class DemographicWidget extends HTMLElement {
    static get observedAttributes() {
        return ["token", "base", "lat", "lng"];
    }

    private root: ShadowRoot;
    private selected: string | null = null;
    private profile: DataResponse | null = null; // last resolved profile (modal source)
    // The last "lat,lng" we resolved, so the two sequential lat/lng attribute
    // writes coalesce into a single /at-point call (see scheduleAtPoint).
    private lastPoint: string | null = null;
    private pointScheduled = false;

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
        // One delegated listener survives every innerHTML re-render: open a
        // category's modal on a tile click, close it on the ✕ / backdrop / Escape.
        this.root.addEventListener("click", (e) => this.onClick(e));
        this.root.addEventListener("keydown", (e) => {
            if ((e as KeyboardEvent).key === "Escape") this.closeModal();
        });
    }

    connectedCallback() {
        this.renderShell();
        // Pick up a point already set before connection (attribute writes while
        // disconnected are ignored by attributeChangedCallback's guard).
        this.scheduleAtPoint();
    }

    attributeChangedCallback(name: string) {
        if (!this.isConnected) return;
        // The widget is driven entirely by the map: a click pushes lat then lng
        // (coalesced into one resolution call). A fresh token (first login, after
        // the widget mounted) just re-arms the pending point — it does NOT redraw,
        // so periodic token refreshes never wipe the shown profile.
        if (name === "token" || name === "lat" || name === "lng") this.scheduleAtPoint();
    }

    // NOTE: these read the host-set attributes, but are deliberately NOT named
    // `base`/`token`. React (19) sets a custom element's matching *property* when
    // one exists; a getter-only `base`/`token` property would make
    // `element.base = ...` throw ("only a getter"). Different names keep those
    // properties absent, so React sets the attributes we observe instead.
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

    // --- map-click resolution ------------------------------------------------

    // The host writes `lat` then `lng` as two synchronous attribute changes; read
    // both once on the next microtask so we issue a single /at-point call with a
    // consistent pair (and skip a point we already resolved).
    private scheduleAtPoint() {
        if (this.pointScheduled) return;
        this.pointScheduled = true;
        queueMicrotask(() => {
            this.pointScheduled = false;
            const lat = this.getAttribute("lat");
            const lng = this.getAttribute("lng");
            if (!lat || !lng) return;
            // No token yet (widget mounted before auth): wait — the token change
            // re-schedules, and lastPoint stays untouched so this point resolves
            // then. A token refresh with an unchanged point is a cheap no-op below.
            if (!this.authToken) return;
            const key = `${lat},${lng}`;
            if (key === this.lastPoint) return;
            this.lastPoint = key;
            void this.loadAtPoint(lat, lng);
        });
    }

    // Resolve the clicked point to its Territory (province, or the national
    // fallback) and show that profile. The resolved name drives the dynamic
    // header. A 503 (boundaries not loaded) / 404 shows a short error in place.
    private async loadAtPoint(lat: string, lng: string) {
        if (!this.root.querySelector(".body")) this.renderShell();
        const body = this.root.querySelector<HTMLElement>(".body");
        if (body) body.innerHTML = `<div class="state">Caricamento…</div>`;
        try {
            const profile = await this.api<DataResponse>(
                `/demographics/at-point?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`,
            );
            this.selected = profile.metadata?.territory_name ?? profile.label ?? null;
            this.renderProfile(profile);
        } catch {
            if (body) {
                body.innerHTML = `<div class="state error">Nessun dato per il punto selezionato.</div>`;
            }
        }
    }

    // --- rendering -----------------------------------------------------------

    // The header is the dynamic selection name (uppercased by CSS); a neutral
    // title stands in until a territory is resolved.
    private headerText(): string {
        return this.selected ?? "Profilo demografico";
    }

    private renderShell() {
        this.root.innerHTML = `
            <style>${STYLES}</style>
            <div class="wrap">
                <header><h2>${this.headerText()}</h2></header>
                <div class="body">
                    <div class="state">${
                        this.selected
                            ? "Caricamento…"
                            : "Seleziona un'area sulla mappa per vedere il profilo demografico."
                    }</div>
                </div>
            </div>
        `;
    }

    private renderProfile(profile: DataResponse) {
        this.profile = profile;
        this.closeModal(); // a fresh selection drops any open modal

        const heading = this.root.querySelector<HTMLElement>("header h2");
        if (heading) heading.textContent = this.headerText();

        const tiles = CATEGORIES.map((cat) => {
            const icon = cat.badge
                ? `<span class="badge">${cat.badge}</span>`
                : `<span class="icon">${cat.icon}</span>`;
            const value = formatValue(profile.data[cat.headline] ?? null, cat.kind);
            return `
                <button class="tile" type="button" data-category="${cat.key}" aria-label="${cat.label}">
                    ${icon}
                    <span class="cat">${cat.label}</span>
                    <span class="value">${value}</span>
                </button>`;
        }).join("");

        const body = this.root.querySelector<HTMLElement>(".body");
        if (body) body.innerHTML = `<div class="tiles">${tiles}</div>`;
    }

    // --- category modal ------------------------------------------------------

    private onClick(e: Event) {
        const target = e.target as HTMLElement;
        if (target.closest("[data-close]") || target.classList.contains("backdrop")) {
            this.closeModal();
            return;
        }
        const tile = target.closest<HTMLElement>("[data-category]");
        if (tile?.dataset.category) this.openModal(tile.dataset.category);
    }

    private openModal(key: string) {
        const cat = CATEGORIES.find((c) => c.key === key);
        if (!cat || !this.profile) return;
        this.closeModal();

        const flags = this.profile.metadata?.quality_flags ?? {};
        const rows = cat.indicators
            .map((ind) => {
                const value = formatValue(this.profile!.data[ind.key] ?? null, cat.kind);
                const flag = flags[ind.key]
                    ? `<span class="flag" title="${QUALITY_LABELS[flags[ind.key]] ?? flags[ind.key]}">${flags[ind.key]}</span>`
                    : "";
                return `<tr><td>${ind.label}</td><td class="value">${value}${flag}</td></tr>`;
            })
            .join("");

        const backdrop = document.createElement("div");
        backdrop.className = "backdrop";
        backdrop.innerHTML = `
            <div class="modal" role="dialog" aria-modal="true" aria-label="${cat.label}">
                <h3>${cat.label}<button class="close" type="button" data-close aria-label="Chiudi">×</button></h3>
                <table><tbody>${rows}</tbody></table>
                <p class="meta">${this.metaLine()}</p>
            </div>`;
        this.root.appendChild(backdrop);
    }

    private closeModal() {
        this.root.querySelector(".backdrop")?.remove();
    }

    private metaLine(): string {
        const meta = this.profile?.metadata;
        return meta
            ? `Popolazione residente al ${meta.population_reference_date ?? "—"} · quote e tassi anno ${
                  meta.rates_reference_year ?? "—"
              }`
            : "";
    }
}

if (!customElements.get("demographic-widget")) {
    customElements.define("demographic-widget", DemographicWidget);
}
