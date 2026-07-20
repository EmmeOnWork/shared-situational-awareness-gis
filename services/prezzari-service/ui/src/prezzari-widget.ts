/**
 * <prezzari-widget> — the I Prezziari dashboard widget, shipped by prezzari-service
 * itself as a self-contained custom element.
 *
 * The FRONTEND half of the full-stack Widget: the service owns both its data
 * (FastAPI /prezzari/locazione + /prezzari/lavori) and its UI (this element). A
 * standard Web Component with no framework, it mounts in ANY host page.
 *
 * It renders TWO reference price lists side by side (CONTEXT.md), never merged or
 * summed — a consultation surface, not a calculator:
 *   LEFT  — Prezziario di Locazione (OMI): the rental quotations of the clicked
 *           comune. Comune-scoped: it re-fetches on each `lat`/`lng` change.
 *   RIGHT — Prezzario dei Lavori: a curated slice of the Regione Campania
 *           public-works price list. Region-fixed: fetched once on mount, it does
 *           NOT change when a different comune is clicked.
 * The two columns degrade INDEPENDENTLY — one empty/errored list never blanks the
 * other. It joins NO selection axis and IGNORES the Active Workshop.
 *
 * Contract with the host (mirrors the sibling widgets):
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 *   attributes `lat`/`lng` — the clicked point every Widget receives.
 */

/** The /prezzari/locazione payload (PRD API contract) — Lista A. */
interface Locazione {
    comune: { region_id: number; name: string };
    publication: string;
    zone: { zona: string; tipologia: string; stato: string; canone_min: number; canone_max: number; um: string }[];
}

/** The /prezzari/lavori payload (PRD API contract) — Lista B. */
interface Lavori {
    publication: string;
    capitoli: { codice: string; titolo: string }[];
    voci: { codice: string; descrizione: string; um: string; prezzo: number; capitolo: string }[];
}

const STYLES = `
    :host { display: block; height: 100%; font-family: system-ui, sans-serif; color: #f9fafb; }
    .wrap { display: flex; flex-direction: column; gap: 8px; height: 100%; padding: 12px; box-sizing: border-box; }
    .cols { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; min-height: 0; }
    .col { display: flex; flex-direction: column; min-height: 0; border: 1px solid rgba(255,255,255,0.12); border-radius: 10px; overflow: hidden; }
    .col header { padding: 8px 10px; background: rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.12); }
    .col h3 { margin: 0; font-size: 12px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 0.03em; }
    .pub { font-size: 11px; color: #94a3b8; }
    .body { flex: 1; overflow: auto; padding: 8px 10px; }
    .state { color: #cbd5e1; font-size: 12px; text-align: center; padding: 16px 8px; }
    .error { color: #fca5a5; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th { text-align: left; color: #94a3b8; font-weight: 600; padding: 4px 6px; border-bottom: 1px solid rgba(255,255,255,0.12); }
    td { padding: 5px 6px; border-bottom: 1px solid rgba(255,255,255,0.06); color: #f9fafb; vertical-align: top; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    .cap { font-size: 11px; color: #94a3b8; }
    .controls { padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.12); display: flex; flex-direction: column; gap: 6px; }
    .capsel { width: 100%; box-sizing: border-box; background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.14); border-radius: 6px; color: #f9fafb; font: inherit; font-size: 12px; padding: 5px 8px; }
    .capsel option, .capsel optgroup { background: #1f2937; color: #f9fafb; }
    .price { font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
`;

class PrezzariWidget extends HTMLElement {
    static get observedAttributes() {
        return ["token", "base", "lat", "lng"];
    }

    private root: ShadowRoot;
    // The last "lat,lng" the left list resolved, so the two sequential lat/lng
    // attribute writes (and a no-op token refresh) coalesce into one fetch.
    private lastPoint: string | null = null;
    private leftScheduled = false;
    // Right-list (region-fixed) filter state. The Capitolo dropdown narrows ONLY
    // the right list; it never re-fetches on a comune click.
    private lavoriCapitolo: string | null = null;
    private lavoriControlsBuilt = false;

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        this.renderShell();
        // The right list (region-fixed) loads once, on mount, before any click.
        void this.loadLavori();
        // The left list (comune-scoped) resolves whatever point is present now.
        this.scheduleLeft();
    }

    attributeChangedCallback(name: string) {
        if (!this.isConnected) return;
        // A new clicked point (or a token refresh) re-fetches ONLY the left list;
        // the right list is region-fixed and never re-fetches on a click.
        if (name === "lat" || name === "lng" || name === "token") this.scheduleLeft();
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

    private authHeaders(): HeadersInit {
        return this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {};
    }

    /** Coalesce the host's lat/lng writes into a single left-list fetch. */
    private scheduleLeft() {
        if (this.leftScheduled) return;
        this.leftScheduled = true;
        queueMicrotask(() => {
            this.leftScheduled = false;
            void this.loadLocazione();
        });
    }

    // --- left list: Prezziario di Locazione (OMI) ----------------------------

    private async loadLocazione() {
        const lat = this.getAttribute("lat");
        const lng = this.getAttribute("lng");
        // No clicked comune yet → the neutral prompt (NOT an error). Also drops the
        // resolve key so a later identical point still fetches.
        if (!lat || !lng) {
            this.lastPoint = null;
            this.renderLeftState("Clicca un comune della Campania sulla mappa.");
            return;
        }
        if (!this.authToken) return; // wait for the host token; a later change re-arms

        const key = `${lat},${lng}`;
        if (key === this.lastPoint) return;
        this.lastPoint = key;

        this.renderLeftState("Caricamento…");
        try {
            const res = await fetch(
                `${this.baseUrl}/prezzari/locazione?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`,
                { headers: this.authHeaders() },
            );
            // A click in no comune (sea / outside Campania) is a 404 → fall back to
            // the neutral prompt, never a broken card.
            if (res.status === 404) {
                this.renderLeftState("Clicca un comune della Campania sulla mappa.");
                return;
            }
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            this.renderLocazione((await res.json()) as Locazione);
        } catch {
            this.renderLeftState("Impossibile caricare le quotazioni OMI.", true);
        }
    }

    private renderLocazione(data: Locazione) {
        const title = `Locazione — ${escapeHtml(data.comune?.name ?? "")}`.trim();
        const pub = data.publication ? `OMI ${escapeHtml(data.publication)}` : "";
        // Comune resolved but no published OMI → the specific empty state, while the
        // right column stays visible (independent degradation).
        if (!data.zone || data.zone.length === 0) {
            this.paintLeft(title, pub, `<div class="state">Quotazioni OMI non disponibili per questo comune.</div>`);
            return;
        }
        const rows = data.zone
            .map(
                (z) => `
                <tr>
                    <td>${escapeHtml(z.zona)}</td>
                    <td>${escapeHtml(z.tipologia)}<div class="cap">${escapeHtml(z.stato)}</div></td>
                    <td class="num">${z.canone_min.toFixed(1)}–${z.canone_max.toFixed(1)}<div class="cap">${escapeHtml(z.um)}</div></td>
                </tr>`,
            )
            .join("");
        this.paintLeft(
            title,
            pub,
            `<table><thead><tr><th>Zona</th><th>Tipologia</th><th class="num">Canone</th></tr></thead><tbody>${rows}</tbody></table>`,
        );
    }

    // --- right list: Prezzario dei Lavori (Regione Campania) -----------------

    private async loadLavori() {
        // `initial` = the on-mount load that also builds the persistent controls
        // (publication label + the Capitolo dropdown). A subsequent filter change
        // repaints ONLY the voci table, leaving the dropdown in place.
        const initial = !this.lavoriControlsBuilt;
        if (initial) this.renderRightState("Caricamento…");
        else this.setVociBody(`<div class="state">Caricamento…</div>`);

        const params = new URLSearchParams();
        if (this.lavoriCapitolo) params.set("capitolo", this.lavoriCapitolo);
        const qs = params.toString();
        try {
            const res = await fetch(
                `${this.baseUrl}/prezzari/lavori${qs ? `?${qs}` : ""}`,
                { headers: this.authHeaders() },
            );
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            this.renderLavori((await res.json()) as Lavori, initial);
        } catch {
            if (initial) this.renderRightState("Impossibile caricare il prezzario dei lavori.", true);
            else this.setVociBody(`<div class="state error">Impossibile caricare il prezzario dei lavori.</div>`);
        }
    }

    private renderLavori(data: Lavori, initial: boolean) {
        if (initial) {
            const pub = data.publication ? `Prezzario ${escapeHtml(data.publication)}` : "";
            this.buildLavoriControls(pub, data.capitoli || []);
        }
        this.setVociBody(this.vociTable(data.voci || []));
    }

    /** The Voce table (or the empty state) — repainted on every filter change. */
    private vociTable(voci: Lavori["voci"]): string {
        if (voci.length === 0) {
            return `<div class="state">Nessuna voce per questo filtro.</div>`;
        }
        const rows = voci
            .map(
                (v) => `
                <tr>
                    <td>${escapeHtml(v.descrizione)}<div class="cap">${escapeHtml(shortCode(v.codice))}</div></td>
                    <td class="num"><span class="price">${formatEuro(v.prezzo)}</span><div class="cap">${escapeHtml(umLabel(v.um))}</div></td>
                </tr>`,
            )
            .join("");
        return `<table><thead><tr><th>Voce</th><th class="num">Prezzo</th></tr></thead><tbody>${rows}</tbody></table>`;
    }

    /** Build the persistent right-column controls once: publication label + a
     *  Capitolo dropdown. Wired to re-fetch the right list only — a comune click
     *  never touches these. */
    private buildLavoriControls(pub: string, capitoli: Lavori["capitoli"]) {
        const col = this.root.getElementById("right");
        if (!col) return;
        const pubEl = col.querySelector(".pub");
        if (pubEl) pubEl.textContent = pub;

        // Readable Capitolo dropdown, grouped by theme parsed from the titolo
        // ("RESTAURO - X" / "RECUPERO - X") — far simpler than 28 code chips.
        const groups = new Map<string, { codice: string; label: string }[]>();
        for (const c of capitoli) {
            const [theme, rest] = splitTitolo(c.titolo);
            if (!groups.has(theme)) groups.set(theme, []);
            groups.get(theme)!.push({ codice: c.codice, label: rest });
        }
        let opts = `<option value="">Tutti i capitoli</option>`;
        for (const [theme, items] of groups) {
            opts += `<optgroup label="${escapeHtml(theme)}">`;
            for (const it of items) {
                opts += `<option value="${escapeHtml(it.codice)}">${escapeHtml(it.label)}</option>`;
            }
            opts += `</optgroup>`;
        }

        const controls = document.createElement("div");
        controls.className = "controls";
        controls.innerHTML = `<select class="capsel" aria-label="Capitolo">${opts}</select>`;
        col.insertBefore(controls, col.querySelector(".body"));

        const sel = controls.querySelector(".capsel") as HTMLSelectElement | null;
        sel?.addEventListener("change", () => {
            this.lavoriCapitolo = sel.value || null;
            void this.loadLavori();
        });
        this.lavoriControlsBuilt = true;
    }

    /** Replace only the right column's Voce table, leaving the controls in place. */
    private setVociBody(html: string) {
        const bodyEl = this.root.getElementById("right")?.querySelector(".body");
        if (bodyEl) bodyEl.innerHTML = html;
    }

    // --- rendering: two independent column bodies ----------------------------

    private renderShell() {
        this.root.innerHTML = `
            <style>${STYLES}</style>
            <div class="wrap">
                <div class="cols">
                    <div class="col" id="left">
                        <header><h3>Prezziario di Locazione</h3><div class="pub"></div></header>
                        <div class="body"><div class="state">Clicca un comune della Campania sulla mappa.</div></div>
                    </div>
                    <div class="col" id="right">
                        <header><h3>Prezzario dei Lavori</h3><div class="pub"></div></header>
                        <div class="body"><div class="state">Caricamento…</div></div>
                    </div>
                </div>
            </div>`;
    }

    private paintLeft(title: string, pub: string, body: string) {
        const col = this.root.getElementById("left");
        if (!col) return;
        const h3 = col.querySelector("h3");
        if (h3) h3.textContent = title || "Prezziario di Locazione";
        this.setColumn(col, pub, body);
    }

    private setColumn(col: HTMLElement, pub: string, body: string) {
        const pubEl = col.querySelector(".pub");
        if (pubEl) pubEl.textContent = pub;
        const bodyEl = col.querySelector(".body");
        if (bodyEl) bodyEl.innerHTML = body;
    }

    private renderLeftState(message: string, isError = false) {
        const col = this.root.getElementById("left");
        if (col) this.setColumn(col, "", stateHtml(message, isError));
    }

    private renderRightState(message: string, isError = false) {
        const col = this.root.getElementById("right");
        if (col) this.setColumn(col, "", stateHtml(message, isError));
    }
}

function stateHtml(message: string, isError: boolean): string {
    return `<div class="state${isError ? " error" : ""}">${escapeHtml(message)}</div>`;
}

function escapeHtml(s: string): string {
    return s.replace(
        /[&<>"']/g,
        (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] as string,
    );
}

/** Drop the edition prefix (e.g. "CAM26_") — the bare voce code is enough as a
 *  muted reference under the description. */
function shortCode(codice: string): string {
    return codice.replace(/^[A-Z]+\d*_/, "");
}

/** Italian-formatted euro price, e.g. 217.67 → "€ 217,67". */
function formatEuro(n: number): string {
    return "€ " + n.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Cryptic prezzario UM abbreviations → a plain-Italian phrase, read as "price <phrase>".
const UM_LABELS: Record<string, string> = {
    mq: "per m²",
    mc: "per m³",
    ml: "per metro",
    m: "per metro",
    cm: "per cm",
    dmc: "per dm³",
    "mq/cm": "per m² (a cm di spessore)",
    kg: "per kg",
    ql: "per quintale",
    q: "per quintale",
    cad: "cadauno",
    n: "cadauno",
    "%": "percentuale",
};

function umLabel(um: string): string {
    const key = (um || "").trim();
    return UM_LABELS[key] ?? UM_LABELS[key.toLowerCase()] ?? um;
}

/** Split a capitolo titolo "RESTAURO - X, Y" into ["Restauro", "X, y"] (nice-cased). */
function splitTitolo(titolo: string): [string, string] {
    const i = titolo.indexOf(" - ");
    if (i < 0) return ["Capitoli", niceCase(titolo)];
    return [niceCase(titolo.slice(0, i)), niceCase(titolo.slice(i + 3))];
}

function niceCase(s: string): string {
    const t = s.trim().toLowerCase();
    return t ? t.charAt(0).toUpperCase() + t.slice(1) : s;
}

if (!customElements.get("prezzari-widget")) {
    customElements.define("prezzari-widget", PrezzariWidget);
}
