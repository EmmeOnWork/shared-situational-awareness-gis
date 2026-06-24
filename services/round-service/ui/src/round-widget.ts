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
 * renders whichever phase the room is in — lobby (join with the account's
 * stakeholder Role, ready, open Round 1), voting (the 16-Vocazione ballot with a
 * confirm modal and the live X/N tally), or the recap (the consensus radar,
 * "consenso totale", and "inizia un nuovo round"). No Active Workshop ⇒ empty state.
 *
 * Contract with the host (mirrors the sibling widgets):
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 */

import { readActiveWorkshop, subscribeActiveWorkshop, type ActiveWorkshop } from "./active-workshop-client";
import { connectRoom, RoundClient, type RoundView } from "./round-client";
import { radarVertices, spokeEnds, consensoTotalePct, type Point } from "./radar";
import { VOCAZIONI } from "./vocazioni";

const STYLES = `
    :host { display: block; height: 100%; font-family: system-ui, sans-serif; color: #f9fafb; }
    .wrap { display: flex; flex-direction: column; height: 100%; padding: 12px; box-sizing: border-box; }
    header { text-align: center; position: relative; }
    .subtitle { font-size: 12px; color: #cbd5e1; padding: 0 64px; box-sizing: border-box; }
    /* The current Round number, always pinned top-right of the widget, every phase. */
    .round-badge { position: absolute; top: 0; right: 0; font-size: 11px; font-weight: 700; color: #93c5fd;
                   background: #1e293b; border: 1px solid #334155; border-radius: 999px; padding: 2px 9px; white-space: nowrap; }
    .body { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 0; gap: 10px; overflow-y: auto; }
    .state { color: #cbd5e1; font-size: 13px; text-align: center; padding: 0 12px; box-sizing: border-box; }
    .big { font-size: 18px; font-weight: 700; color: #ffffff; text-align: center; }
    /* The celebratory phase-4 headline shown when total consensus is reached. */
    .consensus-title { font-size: 21px; font-weight: 800; color: #4ade80; text-align: center; letter-spacing: 0.02em; line-height: 1.15; }
    .tally { font-size: 13px; color: #cbd5e1; }
    .err { color: #fca5a5; font-size: 12px; min-height: 14px; text-align: center; }
    button { font: inherit; font-size: 13px; padding: 7px 14px; border-radius: 8px; border: 1px solid #334155; background: #2563eb; color: #fff; cursor: pointer; }
    button.secondary { background: #1e293b; }
    button:disabled { opacity: 0.5; cursor: default; }
    select { font: inherit; font-size: 13px; padding: 6px 8px; border-radius: 8px; background: #0f172a; color: #f1f5f9; border: 1px solid #334155; max-width: 240px; }
    .roster { font-size: 12px; color: #94a3b8; }
    .hint { font-size: 11px; color: #fbbf24; margin-top: 6px; }
    svg { display: block; }
    .total { font-size: 15px; font-weight: 700; color: #93c5fd; }
    /* The recap radar is a button: click it to open the fullscreen recap. No button
       chrome — it reads as the chart it wraps, with a subtle hover affordance. */
    .radar-btn { background: transparent; border: 0; padding: 4px; margin: 0; cursor: pointer; border-radius: 10px; display: block; }
    .radar-btn:hover { background: rgba(255,255,255,0.06); }
    .radar-hint { font-size: 10px; color: #64748b; }
    .modal { position: absolute; inset: 0; background: rgba(2,6,23,0.78); display: flex; align-items: center; justify-content: center; }
    .card { background: #0f172a; border: 1px solid #334155; border-radius: 12px; padding: 16px; max-width: 260px; text-align: center; display: flex; flex-direction: column; gap: 12px; }
    .row { display: flex; gap: 8px; justify-content: center; }
    .chat { width: 100%; max-width: 280px; margin-top: 4px; display: flex; flex-direction: column; gap: 6px; text-align: left; }
    .chat-head { font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em; color: #94a3b8; }
    .chat-log { display: flex; flex-direction: column; gap: 4px; max-height: 132px; overflow-y: auto; padding-right: 4px; }
    .msg { font-size: 12px; color: #e2e8f0; background: #1e293b; border-radius: 6px; padding: 4px 8px; word-break: break-word; }
    .msg-round { color: #93c5fd; font-size: 10px; font-weight: 700; margin-right: 6px; }
    .chat-empty { font-size: 12px; color: #64748b; }
    .chat-compose { display: flex; gap: 6px; }
    .chat-compose input { flex: 1; min-width: 0; font: inherit; font-size: 12px; padding: 6px 8px; border-radius: 8px; background: #0f172a; color: #f1f5f9; border: 1px solid #334155; }
`;

// Styles for the FULLSCREEN recap modal. It is PORTALED to document.body (see
// syncRecapModal) so the `position: fixed` backdrop escapes the dashboard's grid
// cell — react-grid-layout puts a `transform` on every cell, which would otherwise
// pin a fixed overlay to the cell instead of the viewport (the sibling widgets'
// fullpage pattern). The portal includes STYLES too, so `.total`/`.chat`/`.msg`
// render the same as in-widget.
const MODAL_STYLES = `
    .modal-full { position: fixed; inset: 0; z-index: 2147483000; background: rgba(2,6,23,0.84);
                  display: flex; align-items: center; justify-content: center; padding: 24px; box-sizing: border-box; }
    .recap-card { position: relative; width: 100%; max-width: 940px; max-height: 92vh; overflow-y: auto; box-sizing: border-box;
                  background: #0f172a; border: 1px solid rgba(255,255,255,0.15); border-radius: 14px; padding: 20px 22px; }
    .modal-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
    .modal-head h3 { margin: 0; font-size: 16px; color: #ffffff; }
    .modal-x { background: transparent; border: 0; color: #cbd5e1; font-size: 24px; line-height: 1; padding: 0 6px; cursor: pointer; }
    .modal-x:hover { color: #ffffff; }
    .recap-grid { display: flex; flex-wrap: wrap; gap: 22px; align-items: flex-start; }
    .recap-radar { flex: 1 1 360px; display: flex; flex-direction: column; align-items: center; gap: 10px; min-width: 0; }
    .recap-radar svg { max-width: 100%; height: auto; }
    .recap-chat { flex: 1 1 300px; min-width: 0; }
    .recap-chat .chat { max-width: none; }
    .recap-chat .chat-log { max-height: 52vh; }
    .big-total { font-size: 19px; }
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
    // The account's stakeholder Role, decoded from the host JWT. Absent ⇒ a stale
    // token minted before the claim existed — the server would reject `join`, so the
    // lobby tells the user to re-login instead of offering a doomed Join button.
    private stakeholderRole?: string;
    private selectedVocazione: string = VOCAZIONI[0].id;
    private confirming = false;
    private error = "";
    // The in-progress Chat message, preserved across the full re-render each broadcast
    // triggers (so an incoming message never wipes what you are typing), plus whether
    // the composer had focus (to restore it after the re-paint).
    private chatDraft = "";
    private chatFocused = false;
    // The fullscreen recap modal (opened by clicking the recap radar). It is PORTALED
    // to document.body so its fixed backdrop covers the viewport, not the grid cell.
    // Created on open, torn down on close / phase change / unmount.
    private recapModalOpen = false;
    private modalOverlay?: HTMLElement;
    private modalRoot?: ShadowRoot;
    private prevBodyOverflow = "";

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
    }

    connectedCallback() {
        this.readToken();
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
        this.teardownRecapModal(); // never leave a portal behind in document.body
    }

    attributeChangedCallback(name: string) {
        if (name === "token") {
            this.readToken();
            // Re-open the room with the refreshed token.
            this.teardownRoom();
            this.syncRoom();
        }
        this.render();
    }

    /** Decode `sub` + `stakeholder_role` from the current host token. */
    private readToken() {
        const claims = jwtClaims(this.getAttribute("token"));
        this.userId = claims?.sub != null ? String(claims.sub) : undefined;
        this.stakeholderRole =
            typeof claims?.stakeholder_role === "string" ? claims.stakeholder_role : undefined;
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
            this.syncRecapModal();
            return;
        }
        // The current Round number, pinned top-right in every phase. The lobby (round 0)
        // shows the round it is preparing (1); voting/recap/consensus show their round.
        const badge = this.view
            ? `<div class="round-badge">Round ${Math.max(this.view.round_number, 1)}</div>`
            : "";
        const header = `
            <header>
                ${badge}
                <div class="subtitle">${escapeHtml(this.active.name)}</div>
            </header>`;
        if (!this.view) {
            this.paint(`${header}<div class="body"><div class="state">Connessione alla stanza del Bene…</div></div>`);
            this.syncRecapModal();
            return;
        }
        let body: string;
        if (this.view.phase === "lobby") body = this.renderLobby(this.view);
        else if (this.view.phase === "voting") body = this.renderVoting(this.view);
        else if (this.view.phase === "consensus") body = this.renderConsensus(this.view);
        else body = this.renderRecap(this.view);
        this.paint(`${header}<div class="body">${body}<div class="err">${escapeHtml(this.error)}</div></div>`);
        this.wire();
        // Mount/refresh/tear down the fullscreen recap modal (it mirrors the latest
        // view, so it stays fresh while open and closes itself when we leave recap).
        this.syncRecapModal();
    }

    private renderLobby(view: RoundView): string {
        const me = this.me();
        // The voter count sits BELOW the action in every phase (lobby/voting/recap),
        // so it never jumps above the button as the process moves between phases.
        const roster = `<div class="roster">${view.participants.length} in lobby · ${view.ready_count} pronti</div>`;
        if (!me) {
            // The stakeholder Role comes from the account (JWT claim), so joining is a
            // single action — no in-widget Role declaration.
            return `${this.joinButton("Entra nel round")}${roster}`;
        }
        if (!me.ready) {
            const role = me.role ? `<div class="state">Ruolo: <b>${escapeHtml(me.role)}</b></div>` : "";
            return `${role}<button data-act="ready">Sono pronto</button>${roster}`;
        }
        return `<div class="state">In attesa degli altri…</div>
            ${this.startButton(view, "Avvia il round")}${roster}`;
    }

    /** The Join affordance for a user who is not yet a Participant. Guards the stale
     *  token (no `stakeholder_role` claim): the server would reject `join`, so guide
     *  the user to re-login instead of offering a Join that silently fails. Used by
     *  the lobby AND, mid-process, to reserve a seat in the next Round. */
    private joinButton(label: string): string {
        if (!this.stakeholderRole) {
            return `<div class="state">Ruolo non disponibile sul tuo account.<br/>Esci e rientra per aggiornarlo.</div>`;
        }
        return `<button data-act="join">${escapeHtml(label)}</button>`;
    }

    /** The "open a Round" button, shared by the lobby and the recap. A Round needs
     *  at least two ready Participants (the engine enforces it too), so below that it
     *  is disabled with a hint rather than firing an action the server would reject. */
    private startButton(view: RoundView, label: string): string {
        const enough = view.ready_count >= 2;
        const disabled = enough ? "" : "disabled";
        const hint = enough ? "" : `<div class="hint">Servono almeno 2 partecipanti pronti</div>`;
        return `<button data-act="start" ${disabled}>${label} · ${view.ready_count} pronti</button>${hint}`;
    }

    private renderVoting(view: RoundView): string {
        const tally = `<div class="tally">${view.voted_count}/${view.n} hanno votato</div>`;
        const me = this.me();
        const iVoted = this.userId != null && view.voted_user_ids.includes(this.userId);
        const inRoster = me?.ready ?? false;

        // A roster member of the open Round: cast the ballot, or confirm after voting.
        if (inRoster) {
            if (iVoted) {
                // Vote cast: the anonymous Chat unlocks here — deliberate while the
                // round waits to close (writable until the last vote lands).
                return `<div class="big">HAI VOTATO</div>${tally}<div class="tally">${view.remaining_count}/${view.n} rimasti</div>${this.renderChat(view, true)}`;
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
            return `<div class="big">Esprimi la scelta</div>
                <select data-vocazione>${opts}</select>
                <button data-act="vote-open">Conferma la scelta</button>${tally}${modal}`;
        }

        // A Round is already running and this user is not in its frozen roster. Already
        // a Participant ⇒ they are reserved (they will ready up in the recap). Not yet
        // a Participant ⇒ offer to reserve a seat now (join → Participant for next Round).
        if (me) {
            return `<div class="state">Un round è in corso.<br/>Sei prenotato: parteciperai dal prossimo round.</div>${tally}`;
        }
        return `<div class="state">Un round è già in corso.</div>
            ${this.joinButton("Prenotati per il prossimo round")}${tally}`;
    }

    /** The recap's shared visual: the clickable radar (→ fullscreen details + Chat) and
     *  the pooled "consenso totale". Used by both the recap (which adds a continue
     *  action) and the terminal consensus phase (which does not). The in-card view stays
     *  clean (no inline Chat) — the recap's pre-Chat aesthetic. */
    private recapVisual(view: RoundView): string {
        const recap = view.recap;
        if (!recap) return "";
        return `<button class="radar-btn" data-act="open-recap" aria-label="Apri il recap a schermo intero">
                    ${this.renderRadar(recap.radar)}
               </button>
               <div class="radar-hint">clicca il grafico per i dettagli</div>
               <div class="total">consenso totale ${consensoTotalePct(recap.overall)}</div>`;
    }

    private renderRecap(view: RoundView): string {
        // Same voter count as the lobby, BELOW the action — the recap is the next
        // Round's lobby (join → ready → start), so it carries the same count.
        const roster = `<div class="roster">${view.participants.length} in lobby · ${view.ready_count} pronti</div>`;
        const me = this.me();
        // One button at a time, like the lobby: a non-Participant joins first (clicking
        // "ready" without joining is a server no-op), then readies, then (once ready)
        // opens the next Round. Avoids the earlier two-buttons-that-look-the-same issue.
        let action: string;
        if (!me) {
            action = this.joinButton("Unisciti al prossimo round");
        } else if (!me.ready) {
            action = `<button data-act="ready">Sono pronto a ricominciare</button>`;
        } else {
            action = this.startButton(view, "Inizia un nuovo round");
        }
        return `${this.recapVisual(view)}${action}${roster}`;
    }

    /** The terminal phase — consensus reached. Identical to the recap (the same radar →
     *  fullscreen details + Chat, and consenso totale, which is 100% here) but with NO
     *  action: the process is settled, there is nothing to continue. */
    private renderConsensus(view: RoundView): string {
        const roster = `<div class="roster">${view.participants.length} in lobby · ${view.ready_count} pronti</div>`;
        // The big phase-4 headline (the celebratory moment the recap doesn't have),
        // above the same radar + consenso totale; no action follows — it is terminal.
        const title = `<div class="consensus-title">Consenso raggiunto</div>`;
        return `${title}${this.recapVisual(view)}${roster}`;
    }

    /** The fullscreen recap, portaled to document.body (syncRecapModal). The big radar
     *  carries per-Role headcounts ("3 tecnici") and each subgroup's intra-Role
     *  consensus %, beside the read-only deliberation Chat. The backdrop and the × close
     *  it; a phase change or unmount tears it down. */
    private renderRecapModal(view: RoundView): string {
        const recap = view.recap;
        if (!recap) return "";
        const radar = this.renderRadar(recap.radar, { size: 300, pad: 64, detailed: true });
        const total = `<div class="total big-total">consenso totale ${consensoTotalePct(recap.overall)}</div>`;
        return `<div class="modal-full" data-backdrop>
            <div class="recap-card">
                <div class="modal-head">
                    <h3>${escapeHtml(this.active?.name ?? "Recap")} · Round ${view.round_number}</h3>
                    <button class="modal-x" data-act="close-recap" aria-label="Chiudi">×</button>
                </div>
                <div class="recap-grid">
                    <div class="recap-radar">${radar}${total}</div>
                    <div class="recap-chat">${this.renderChat(view, false)}</div>
                </div>
            </div>
        </div>`;
    }

    /** The anonymous per-Bene deliberation Chat. The full continuous stream the
     *  server sends (already anonymised — no author — and already gated: empty unless
     *  this client may read it), each line tagged with the Round it was posted in. A
     *  composer is shown only when ``canPost`` (after voting, in the open Round); the
     *  recap is read-only. */
    private renderChat(view: RoundView, canPost: boolean): string {
        const messages = view.chat ?? [];
        const log = messages.length
            ? messages
                  .map(
                      (m) =>
                          `<div class="msg"><span class="msg-round">R${m.round_number}</span>${escapeHtml(m.body)}</div>`,
                  )
                  .join("")
            : `<div class="chat-empty">Nessun messaggio.</div>`;
        const composer = canPost
            ? `<div class="chat-compose">
                    <input data-chat-input type="text" maxlength="500" placeholder="Messaggio anonimo…" />
                    <button class="secondary" data-act="chat-send">Invia</button>
               </div>`
            : "";
        return `<div class="chat">
            <div class="chat-head">Chat anonima</div>
            <div class="chat-log">${log}</div>
            ${composer}
        </div>`;
    }

    /** Build the recap radar SVG: a spoke per Role present, the polygon through the
     *  per-Role consensus vertices, and each Role's label at the rim. `detailed` (the
     *  fullscreen modal) labels each spoke with the Role's headcount ("3 tecnici") and
     *  its intra-group consensus %, pushed out past the rim into the `pad` margin so the
     *  longer labels never overlap the chart. */
    private renderRadar(
        branches: { role: string; consensus: number; count?: number }[],
        opts: { size?: number; pad?: number; detailed?: boolean } = {},
    ): string {
        const size = opts.size ?? 180;
        const pad = opts.pad ?? 0;
        const detailed = opts.detailed ?? false;
        const c = size / 2;
        const r = c - (detailed ? 30 : 26);
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
        // Detailed labels sit a little beyond the rim so the two-line text clears the chart.
        const labelPts = detailed ? spokeEnds(branches.length, c, c, r + 16) : ends;
        const labels = labelPts
            .map((p, i) => {
                const b = branches[i];
                const lx = fmt(labelX(p, c));
                const a = anchor(p, c);
                if (!detailed) {
                    return `<text x="${lx}" y="${fmt(p.y)}" font-size="9" fill="#94a3b8" text-anchor="${a}">${escapeHtml(b.role)}</text>`;
                }
                const head = `${b.count ?? 0} ${roleLabel(b.role, b.count ?? 0)}`;
                return `<text x="${lx}" y="${fmt(p.y)}" text-anchor="${a}">
                    <tspan x="${lx}" dy="0" font-size="12" font-weight="700" fill="#e2e8f0">${escapeHtml(head)}</tspan>
                    <tspan x="${lx}" dy="13" font-size="10" fill="#93c5fd">consenso ${consensoTotalePct(b.consensus)}</tspan>
                </text>`;
            })
            .join("");
        const vb = `${-pad} ${-pad} ${size + 2 * pad} ${size + 2 * pad}`;
        const dim = size + 2 * pad;
        return `<svg viewBox="${vb}" width="${dim}" height="${dim}" role="img" aria-label="radar del consenso per ruolo">
            ${ring}${grid}${polygon}${labels}
        </svg>`;
    }

    private paint(body: string) {
        this.root.innerHTML = `<style>${STYLES}</style><div class="wrap" style="position:relative">${body}</div>`;
    }

    /** Attach listeners after each paint (the markup is re-rendered each view). */
    private wire() {
        const root = this.root;
        const vocSel = root.querySelector<HTMLSelectElement>("select[data-vocazione]");
        vocSel?.addEventListener("change", () => (this.selectedVocazione = vocSel.value));

        root.querySelectorAll<HTMLButtonElement>("button[data-act]").forEach((btn) => {
            btn.addEventListener("click", () => this.act(btn.dataset.act!));
        });

        this.wireChat(root);
    }

    /** Re-bind the Chat composer after each paint: restore the in-progress draft (and
     *  focus/caret, if it had focus) so a broadcast mid-typing is non-destructive, and
     *  keep the log pinned to the latest message. */
    private wireChat(root: ShadowRoot) {
        const input = root.querySelector<HTMLInputElement>("input[data-chat-input]");
        if (input) {
            input.value = this.chatDraft;
            input.addEventListener("input", () => (this.chatDraft = input.value));
            input.addEventListener("focus", () => (this.chatFocused = true));
            input.addEventListener("blur", () => (this.chatFocused = false));
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    e.preventDefault();
                    this.sendChat();
                }
            });
            if (this.chatFocused) {
                input.focus();
                const end = input.value.length;
                input.setSelectionRange(end, end);
            }
        }
        const log = root.querySelector<HTMLElement>(".chat-log");
        if (log) log.scrollTop = log.scrollHeight;
    }

    /** Send the current draft as an anonymous Chat message and clear it. The server's
     *  broadcast re-renders the view (with the new message); focus is preserved by
     *  ``wireChat`` so a quick back-and-forth needs no re-click. */
    private sendChat() {
        const body = this.chatDraft.trim();
        if (!body || !this.client) return;
        this.client.chat(body);
        this.chatDraft = "";
        const input = this.root.querySelector<HTMLInputElement>("input[data-chat-input]");
        if (input) input.value = "";
    }

    /** Mount / refresh / tear down the fullscreen recap modal in a portal on
     *  document.body. The portal escapes the dashboard's transformed grid cell so the
     *  `position: fixed` backdrop covers the real viewport. Open only while the modal is
     *  requested AND we are in the recap phase; any other phase (a new round) or unmount
     *  closes it. The delegated click listener (added once) handles the backdrop + ×
     *  close and survives each innerHTML refresh. */
    private syncRecapModal() {
        const view = this.view;
        const inRecapLike = view?.phase === "recap" || view?.phase === "consensus";
        const open = this.recapModalOpen && inRecapLike && view.recap != null;
        if (!open) {
            this.teardownRecapModal();
            return;
        }
        if (!this.modalOverlay) {
            this.modalOverlay = document.createElement("div");
            this.modalRoot = this.modalOverlay.attachShadow({ mode: "open" });
            this.modalRoot.addEventListener("click", (e) => {
                const t = e.target as HTMLElement;
                if (t.hasAttribute("data-backdrop") || t.closest("[data-act='close-recap']")) {
                    this.closeRecapModal();
                }
            });
            this.prevBodyOverflow = document.body.style.overflow;
            document.body.style.overflow = "hidden"; // lock the page behind the modal
            document.body.appendChild(this.modalOverlay);
        }
        this.modalRoot!.innerHTML = `<style>${STYLES}${MODAL_STYLES}</style>${this.renderRecapModal(view!)}`;
        const log = this.modalRoot!.querySelector<HTMLElement>(".chat-log");
        if (log) log.scrollTop = log.scrollHeight;
    }

    private closeRecapModal() {
        this.recapModalOpen = false;
        this.teardownRecapModal();
    }

    private teardownRecapModal() {
        if (!this.modalOverlay) return;
        this.modalOverlay.remove();
        this.modalOverlay = undefined;
        this.modalRoot = undefined;
        document.body.style.overflow = this.prevBodyOverflow; // unlock the page
    }

    private act(action: string) {
        // UI-local actions (no server round-trip): the fullscreen recap modal.
        if (action === "open-recap") {
            this.recapModalOpen = true;
            this.render();
            return;
        }
        if (action === "close-recap") {
            this.closeRecapModal();
            return;
        }
        const client = this.client;
        if (!client) return;
        switch (action) {
            case "join": client.join(); break;
            case "ready": client.ready(); break;
            case "start": client.start(); break;
            case "vote-open": this.confirming = true; this.render(); break;
            case "vote-cancel": this.confirming = false; this.render(); break;
            case "vote-confirm":
                this.confirming = false;
                client.vote(this.selectedVocazione);
                break;
            case "chat-send": this.sendChat(); break;
        }
    }
}

/** Decode a JWT's payload without verifying it — the element only needs to read
 *  `sub` (which roster row is "me") and `stakeholder_role` (the account Role the
 *  server seeds on join); the server enforces identity and the role for real. */
function jwtClaims(token: string | null): Record<string, unknown> | undefined {
    if (!token) return undefined;
    try {
        const part = token.split(".")[1];
        const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
        return JSON.parse(json) as Record<string, unknown>;
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

// Italian plural of each stakeholder Role, for the fullscreen radar's headcount label
// ("1 tecnico" / "3 tecnici"). The three Roles are a closed catalog; an unknown Role
// falls back to its raw value.
const ROLE_PLURALS: Record<string, string> = {
    tecnico: "tecnici",
    istituzionale: "istituzionali",
    economico: "economici",
};
const roleLabel = (role: string, count: number): string =>
    count === 1 ? role : (ROLE_PLURALS[role] ?? role);

if (!customElements.get("round-widget")) {
    customElements.define("round-widget", RoundWidget);
}
