/**
 * <round-widget> — the Round Manager dashboard widget, shipped by the
 * round-service itself as a self-contained custom element.
 *
 * The FRONTEND half of the full-stack Widget: the service owns both its data
 * (FastAPI /rounds/*, the per-Bene WebSocket room) and its UI (this element). A
 * standard Web Component with no framework, it mounts in ANY host page.
 *
 * SENSITIVE (ADR-0003): it CONSUMES the Active Workshop (never publishes it). With
 * a Bene selected and a host JWT present it opens that Bene's realtime room and
 * renders whichever phase the room is in — lobby (join, declare stakeholder Role,
 * ready, open Round 1), voting (the 16-Vocazione ballot with a confirm modal and
 * the live X/N tally), or the recap (the consensus radar, "consenso totale", and
 * "inizia un nuovo round"). No Active Workshop ⇒ empty state.
 *
 * Contract with the host (mirrors the sibling widgets):
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 */

import { readActiveWorkshop, subscribeActiveWorkshop, type ActiveWorkshop } from "./active-workshop-client";
import { connectRoom, RoundClient, type RoundView } from "./round-client";
import { radarVertices, spokeEnds, consensoTotalePct, type Point } from "./radar";
import { VOCAZIONI } from "./vocazioni";

// The small stakeholder-Role catalog the service owns (the radar's branches; the
// grouping for intra-Role Consensus). Mirrors the backend ROLE_CATALOG — copied,
// not imported (each Widget ships self-contained, service ADR-0001).
const STAKEHOLDER_ROLES = ["istituzionale", "economico", "tecnico", "sociale", "ambientale"] as const;

const STYLES = `
    :host { display: block; height: 100%; font-family: system-ui, sans-serif; color: #f9fafb; }
    .wrap { display: flex; flex-direction: column; height: 100%; padding: 12px; box-sizing: border-box; }
    header { text-align: center; }
    h2 { font-size: 15px; font-weight: 700; margin: 0; color: #ffffff; letter-spacing: 0.03em; text-transform: uppercase; }
    .subtitle { margin-top: 2px; font-size: 12px; color: #cbd5e1; }
    .body { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 0; gap: 10px; }
    .state { color: #cbd5e1; font-size: 13px; text-align: center; padding: 0 12px; box-sizing: border-box; }
    .big { font-size: 18px; font-weight: 700; color: #ffffff; text-align: center; }
    .tally { font-size: 13px; color: #cbd5e1; }
    .err { color: #fca5a5; font-size: 12px; min-height: 14px; text-align: center; }
    button { font: inherit; font-size: 13px; padding: 7px 14px; border-radius: 8px; border: 1px solid #334155; background: #2563eb; color: #fff; cursor: pointer; }
    button.secondary { background: #1e293b; }
    button:disabled { opacity: 0.5; cursor: default; }
    select { font: inherit; font-size: 13px; padding: 6px 8px; border-radius: 8px; background: #0f172a; color: #f1f5f9; border: 1px solid #334155; max-width: 240px; }
    .roster { font-size: 12px; color: #94a3b8; }
    svg { display: block; }
    .total { font-size: 15px; font-weight: 700; color: #93c5fd; }
    .modal { position: absolute; inset: 0; background: rgba(2,6,23,0.78); display: flex; align-items: center; justify-content: center; }
    .card { background: #0f172a; border: 1px solid #334155; border-radius: 12px; padding: 16px; max-width: 260px; text-align: center; display: flex; flex-direction: column; gap: 12px; }
    .row { display: flex; gap: 8px; justify-content: center; }
`;

class RoundWidget extends HTMLElement {
    static get observedAttributes() {
        return ["token", "base"];
    }

    private root: ShadowRoot;
    private active?: ActiveWorkshop;
    private unsubscribe?: () => void;

    // Live room connection + the latest view it pushed.
    private client?: RoundClient;
    private closeRoom?: () => void;
    private view?: RoundView;
    private connectedPoiId?: number;

    // UI-local (not server) state.
    private userId?: string;
    private selectedRole: string = STAKEHOLDER_ROLES[0];
    private selectedVocazione: string = VOCAZIONI[0].id;
    private confirming = false;
    private error = "";

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        this.userId = jwtSub(this.getAttribute("token"));
        this.active = readActiveWorkshop();
        this.unsubscribe = subscribeActiveWorkshop((workshop) => {
            this.active = workshop;
            this.syncRoom();
            this.render();
        });
        this.syncRoom();
        this.render();
    }

    disconnectedCallback() {
        this.unsubscribe?.();
        this.unsubscribe = undefined;
        this.teardownRoom();
    }

    attributeChangedCallback(name: string) {
        if (name === "token") {
            this.userId = jwtSub(this.getAttribute("token"));
            // Re-open the room with the refreshed token.
            this.teardownRoom();
            this.syncRoom();
        }
        this.render();
    }

    /** Open/close the Bene's room so the live connection always matches the
     *  Active Workshop (re-subscribes on switch, closes on no-Bene). */
    private syncRoom() {
        const poiId = this.active?.poiId;
        const token = this.getAttribute("token");
        if (poiId == null || !token) {
            this.teardownRoom();
            return;
        }
        if (this.connectedPoiId === poiId && this.client) {
            return; // already on this Bene
        }
        this.teardownRoom();
        const base = this.getAttribute("base") ?? "";
        const { client, close } = connectRoom(
            base,
            poiId,
            token,
            (view) => {
                this.view = view;
                this.error = "";
                this.render();
            },
            (detail) => {
                this.error = detail;
                this.render();
            },
        );
        this.client = client;
        this.closeRoom = close;
        this.connectedPoiId = poiId;
    }

    private teardownRoom() {
        this.closeRoom?.();
        this.closeRoom = undefined;
        this.client = undefined;
        this.connectedPoiId = undefined;
        this.view = undefined;
    }

    private me() {
        return this.view?.participants.find((p) => p.user_id === this.userId);
    }

    private render() {
        if (!this.active) {
            this.paint(`<div class="body"><div class="state">Seleziona un Bene per avviare il round.</div></div>`);
            return;
        }
        const header = `
            <header>
                <h2>Round Manager</h2>
                <div class="subtitle">${escapeHtml(this.active.name)}</div>
            </header>`;
        if (!this.view) {
            this.paint(`${header}<div class="body"><div class="state">Connessione alla stanza del Bene…</div></div>`);
            return;
        }
        let body: string;
        if (this.view.phase === "lobby") body = this.renderLobby(this.view);
        else if (this.view.phase === "voting") body = this.renderVoting(this.view);
        else body = this.renderRecap(this.view);
        this.paint(`${header}<div class="body">${body}<div class="err">${escapeHtml(this.error)}</div></div>`);
        this.wire();
    }

    private renderLobby(view: RoundView): string {
        const me = this.me();
        const roster = `<div class="roster">${view.participants.length} in lobby · ${view.ready_count} pronti</div>`;
        if (!me) {
            return `${roster}<button data-act="join">Entra nel round</button>`;
        }
        if (!me.role) {
            const opts = STAKEHOLDER_ROLES.map(
                (r) => `<option value="${r}" ${r === this.selectedRole ? "selected" : ""}>${r}</option>`,
            ).join("");
            return `${roster}<div class="state">Dichiara il tuo ruolo</div>
                <select data-role>${opts}</select>
                <button data-act="declare">Conferma ruolo</button>`;
        }
        if (!me.ready) {
            return `${roster}<div class="state">Ruolo: <b>${escapeHtml(me.role)}</b></div>
                <button data-act="ready">Sono pronto</button>`;
        }
        return `${roster}<div class="state">In attesa degli altri…</div>
            <button data-act="start">Avvia il round · ${view.ready_count} pronti</button>`;
    }

    private renderVoting(view: RoundView): string {
        const tally = `<div class="tally">${view.voted_count}/${view.n} hanno votato</div>`;
        const iVoted = this.userId != null && view.voted_user_ids.includes(this.userId);
        const inRoster = this.me()?.ready ?? false;
        if (iVoted || !inRoster) {
            const note = iVoted
                ? `<div class="big">HAI VOTATO</div><div class="tally">${view.remaining_count}/${view.n} rimasti</div>`
                : `<div class="state">Voto nel prossimo round (sei entrato a round avviato).</div>`;
            return `${tally}${note}`;
        }
        const opts = VOCAZIONI.map(
            (v) => `<option value="${v.id}" ${v.id === this.selectedVocazione ? "selected" : ""}>${escapeHtml(v.label)}</option>`,
        ).join("");
        const modal = this.confirming
            ? `<div class="modal"><div class="card">
                    <div>Confermi il voto? È <b>definitivo</b>.</div>
                    <div class="row">
                        <button data-act="vote-confirm">Conferma</button>
                        <button class="secondary" data-act="vote-cancel">Annulla</button>
                    </div>
               </div></div>`
            : "";
        return `${tally}<div class="big">Esprimi la scelta</div>
            <select data-vocazione>${opts}</select>
            <button data-act="vote-open">Conferma la scelta</button>${modal}`;
    }

    private renderRecap(view: RoundView): string {
        const recap = view.recap;
        const radar = recap ? this.renderRadar(recap.radar) : "";
        const total = recap ? `<div class="total">consenso totale ${consensoTotalePct(recap.overall)}</div>` : "";
        const me = this.me();
        const readyBtn = me?.ready ? "" : `<button class="secondary" data-act="ready">Sono pronto a ricominciare</button>`;
        return `${radar}${total}${readyBtn}
            <button data-act="start">Inizia un nuovo round · ${view.ready_count} pronti</button>`;
    }

    /** Build the recap radar SVG: a spoke per Role present, the polygon through the
     *  per-Role consensus vertices, and each Role's label at the rim. */
    private renderRadar(branches: { role: string; consensus: number }[]): string {
        const size = 180;
        const c = size / 2;
        const r = c - 26;
        if (branches.length === 0) {
            return `<div class="state">Nessun voto registrato.</div>`;
        }
        const verts = radarVertices(branches, c, c, r);
        const ends = spokeEnds(branches.length, c, c, r);
        const grid = ends
            .map((p) => `<line x1="${c}" y1="${c}" x2="${fmt(p.x)}" y2="${fmt(p.y)}" stroke="#334155" stroke-width="1"/>`)
            .join("");
        const ring = `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="#1e293b" stroke-width="1"/>`;
        const polygon =
            branches.length >= 2
                ? `<polygon points="${verts.map((p) => `${fmt(p.x)},${fmt(p.y)}`).join(" ")}" fill="rgba(37,99,235,0.35)" stroke="#3b82f6" stroke-width="2"/>`
                : `<circle cx="${fmt(verts[0].x)}" cy="${fmt(verts[0].y)}" r="4" fill="#3b82f6"/>`;
        const labels = ends
            .map((p, i) => `<text x="${fmt(labelX(p, c))}" y="${fmt(p.y)}" font-size="9" fill="#94a3b8" text-anchor="${anchor(p, c)}">${escapeHtml(branches[i].role)}</text>`)
            .join("");
        return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" role="img" aria-label="radar del consenso per ruolo">
            ${ring}${grid}${polygon}${labels}
        </svg>`;
    }

    private paint(body: string) {
        this.root.innerHTML = `<style>${STYLES}</style><div class="wrap" style="position:relative">${body}</div>`;
    }

    /** Attach listeners after each paint (the markup is re-rendered each view). */
    private wire() {
        const root = this.root;
        const roleSel = root.querySelector<HTMLSelectElement>("select[data-role]");
        roleSel?.addEventListener("change", () => (this.selectedRole = roleSel.value));
        const vocSel = root.querySelector<HTMLSelectElement>("select[data-vocazione]");
        vocSel?.addEventListener("change", () => (this.selectedVocazione = vocSel.value));

        root.querySelectorAll<HTMLButtonElement>("button[data-act]").forEach((btn) => {
            btn.addEventListener("click", () => this.act(btn.dataset.act!));
        });
    }

    private act(action: string) {
        const client = this.client;
        if (!client) return;
        switch (action) {
            case "join": client.join(); break;
            case "declare": client.declareRole(this.selectedRole); break;
            case "ready": client.ready(); break;
            case "start": client.start(); break;
            case "vote-open": this.confirming = true; this.render(); break;
            case "vote-cancel": this.confirming = false; this.render(); break;
            case "vote-confirm":
                this.confirming = false;
                client.vote(this.selectedVocazione);
                break;
        }
    }
}

/** Decode the `sub` (user_id) from a JWT without verifying it — the element only
 *  needs to know which roster row is "me"; the server enforces identity. */
function jwtSub(token: string | null): string | undefined {
    if (!token) return undefined;
    try {
        const part = token.split(".")[1];
        const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
        const payload = JSON.parse(json);
        return payload.sub != null ? String(payload.sub) : undefined;
    } catch {
        return undefined;
    }
}

const fmt = (n: number): string => Number(n.toFixed(2)).toString();
const labelX = (p: Point, c: number): number => (Math.abs(p.x - c) < 1 ? p.x : p.x > c ? p.x + 3 : p.x - 3);
const anchor = (p: Point, c: number): string => (Math.abs(p.x - c) < 1 ? "middle" : p.x > c ? "start" : "end");

function escapeHtml(s: string): string {
    return s.replace(
        /[&<>"']/g,
        (ch) =>
            ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch] as string,
    );
}

if (!customElements.get("round-widget")) {
    customElements.define("round-widget", RoundWidget);
}
