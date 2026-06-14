/**
 * <characteristic-widget> — the Building Characteristic dashboard widget, shipped
 * by the characteristic-service itself as a self-contained custom element.
 *
 * This is the FRONTEND half of the full-stack Widget: the service owns both its
 * data (FastAPI /characteristic/*) and its UI (this element). It is a standard
 * Web Component with no framework, so it mounts in ANY host page — the Janus
 * monolith today, anything tomorrow — which is what makes the Widget reusable and
 * independent of the monolith (the strangler-fig end state).
 *
 * The element is SENSITIVE (ADR-0003): it reads the retained Active Workshop at
 * mount and subscribes to the praim:workshop-selected bus via the client module,
 * then fetches the light frame (GET /characteristic/workshops/{poiId}). It renders
 * the states from there — the Load form (Blueprint upload + the Scheda fields), the
 * lazily-loaded Blueprint in the centre, and the Scheda modal opened by clicking it
 * (State 4: "non disponibile" when the Scheda has never been filled).
 *
 * Contract with the host (see docs/architecture/widget-microservice-fullstack.md):
 *   attribute `token` — the monolith-issued JWT; the host sets and refreshes it.
 *   attribute `base`  — the edge-gateway origin; "" means same origin.
 * The element calls only its OWN service's routes, always through the gateway,
 * always with the host's JWT. It never reaches the monolith. Comune/coordinates
 * come from the Active Workshop bus `detail` (the POI is their source of truth,
 * decision A) — never re-fetched or re-stored here.
 */

import { readActiveWorkshop, subscribeActiveWorkshop, type ActiveWorkshop } from "./active-workshop-client";
import {
    buildSchedaPayload,
    isSchedaEmpty,
    type Scheda,
    TITOLO_VALUES,
    STATO_USO_VALUES,
    CONDIZIONI_VALUES,
    VINCOLI_VALUES,
} from "./scheda";

/** One Blueprint in the light listing from GET /characteristic/workshops/{poiId}. */
interface BlueprintMeta {
    id: number;
    sezione: string;
}

/** The light Active Workshop frame: the Scheda (null until the first Load creates
 *  it) + the Sezione listing. Bytea-free — the image is fetched separately by id. */
interface WorkshopFrame {
    scheda: Scheda | null;
    blueprints: BlueprintMeta[];
}

/** One Planimetria row's restorable state: its Sezione text and the chosen image
 *  File. The File is re-attached to the row's file input on reopen via DataTransfer,
 *  so dismissing the modal keeps the full upload state, image included. */
interface SezioneDraft {
    sezione: string;
    file: File | null;
}

/** The Scheda's free-text + enum fields, in form order. ``vincoli`` is handled
 *  separately (a checkbox group), so it is intentionally absent here. Drives both
 *  the Load form's inputs and the modal read-out, so the two never drift. */
const SCHEDA_FIELDS: ReadonlyArray<{ name: keyof Scheda; label: string; enum?: readonly string[] }> = [
    { name: "denominazione", label: "Denominazione" },
    { name: "destinazione_uso", label: "Destinazione d'uso" },
    { name: "titolo", label: "Titolo di disponibilità", enum: TITOLO_VALUES },
    { name: "titolo_estremi", label: "Estremi del titolo" },
    { name: "stato_uso", label: "Stato d'uso", enum: STATO_USO_VALUES },
    { name: "condizioni", label: "Condizioni", enum: CONDIZIONI_VALUES },
    { name: "stato_descrizione", label: "Descrizione dello stato" },
    { name: "vincoli_note", label: "Note sui vincoli" },
    { name: "foglio", label: "Foglio (catasto)" },
    { name: "particella", label: "Particella (catasto)" },
    { name: "referente_nome", label: "Referente — nome" },
    { name: "referente_email", label: "Referente — email" },
    { name: "referente_tel", label: "Referente — telefono" },
];

const STYLES = `
    :host { display: block; position: relative; height: 100%; font-family: system-ui, sans-serif; color: #f9fafb; }
    .wrap { display: flex; flex-direction: column; gap: 12px; height: 100%; padding: 12px; box-sizing: border-box; }
    header { text-align: center; }
    h2 { font-size: 15px; font-weight: 700; margin: 0; color: #ffffff; letter-spacing: 0.03em; text-transform: uppercase; }
    .subtitle { margin-top: 2px; font-size: 12px; color: #cbd5e1; }
    .coords { font-size: 11px; color: #94a3b8; }
    .body { position: relative; flex: 1; display: flex; min-height: 0; align-items: center; justify-content: center; }
    .state { color: #cbd5e1; font-size: 13px; text-align: center; padding: 0 12px; box-sizing: border-box; }
    .load { padding: 8px 14px; border: 1px solid rgba(255,255,255,0.18); border-radius: 8px; background: rgba(255,255,255,0.05);
            color: #f9fafb; font: inherit; font-size: 13px; cursor: pointer; }
    .load:hover { background: rgba(255,255,255,0.10); }
    .load.faded { opacity: 0.4; cursor: not-allowed; }
    .load.small { position: absolute; top: 0; left: 0; padding: 5px 10px; font-size: 12px; }
    .load.primary { position: absolute; top: 30%; left: 50%; transform: translate(-50%, -50%); }
    .load.remove { top: auto; bottom: 0; left: 0; border-color: rgba(252,165,165,0.4); color: #fca5a5; }
    .load.remove:hover { background: rgba(252,165,165,0.12); }
    /* State 3 (image loaded): controls live in the header bar — Load + Rimuovi on the
       left, the Sezione dropdown on the right, the title centred between them. The
       1fr/auto/1fr columns keep the two sides symmetric, freeing the body for the image. */
    header.bar { display: grid; grid-template-columns: 1fr auto 1fr; align-items: start; gap: 8px; }
    .bar-side { display: flex; gap: 6px; align-items: flex-start; }
    .bar-side.right { justify-content: flex-end; }
    .bar-side .load.small { position: static; }
    .bar-center { text-align: center; min-width: 0; }
    .sezioni-select { max-width: 100%; padding: 5px 9px; border: 1px solid rgba(255,255,255,0.18); border-radius: 6px;
                      background: rgba(255,255,255,0.06); color: #f9fafb; font: inherit; font-size: 12px; cursor: pointer; }
    .sezioni-select option { color: #111827; background: #ffffff; }
    .placeholder { color: #64748b; font-size: 12px; }
    .error { color: #fca5a5; }
    .image { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 6px; }
    .form { display: flex; flex-direction: column; gap: 10px; width: 100%; max-width: 280px; max-height: 100%; overflow-y: auto; padding-right: 4px; box-sizing: border-box; }
    .form .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px 14px; }
    .form .sezioni-list { display: flex; flex-direction: column; gap: 10px; }
    .form .sezione-row { display: flex; align-items: flex-end; gap: 8px; }
    .form .sezione-row .grid2 { flex: 1; }
    .form .row-remove { flex: none; width: 30px; height: 32px; border: 1px solid rgba(252,165,165,0.4);
                        border-radius: 6px; background: rgba(255,255,255,0.05); color: #fca5a5; font-size: 16px;
                        line-height: 1; cursor: pointer; }
    .form .row-remove:hover { background: rgba(252,165,165,0.12); }
    .form .load.add { align-self: flex-start; padding: 5px 10px; font-size: 12px; }
    .form label { font-size: 12px; color: #cbd5e1; display: flex; flex-direction: column; gap: 4px; text-align: left; }
    .form input[type=text], .form select { padding: 6px 8px; border: 1px solid rgba(255,255,255,0.18); border-radius: 6px;
                             background: rgba(255,255,255,0.05); color: #f9fafb; font: inherit; font-size: 13px; }
    .form select option { color: #111827; background: #ffffff; }
    .form .altro { margin-top: 6px; }
    .form .altro[hidden] { display: none; }
    .form .vincoli .altro { width: 100%; box-sizing: border-box; }
    .form input[type=file] { font-size: 12px; color: #cbd5e1; }
    .form .section { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; margin-top: 4px; text-align: left; }
    .form .vincoli { border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; padding: 6px 10px; margin: 0; display: flex; flex-direction: column; gap: 4px; }
    .form .vincoli legend { font-size: 11px; color: #94a3b8; padding: 0 4px; }
    .form .check { flex-direction: row; align-items: center; gap: 6px; font-size: 12px; }
    .form .actions { display: flex; gap: 8px; justify-content: flex-end; }
    .form .ghost { background: transparent; }
    .modal { position: absolute; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center;
             background: rgba(2,6,23,0.7); padding: 12px; box-sizing: border-box; }
    .modal-card { width: 100%; max-width: 320px; max-height: 100%; overflow-y: auto; text-align: left; box-sizing: border-box;
                  background: #0f172a; border: 1px solid rgba(255,255,255,0.15); border-radius: 10px; padding: 14px; }
    .modal-card h3 { margin: 0 0 10px; font-size: 14px; color: #ffffff; }
    .modal-card .actions { display: flex; justify-content: flex-end; margin-top: 12px; }
    .readout { display: flex; flex-direction: column; gap: 8px; }
    .readout .row { display: flex; flex-direction: column; gap: 1px; }
    .readout .k { font-size: 11px; color: #94a3b8; }
    .readout .v { font-size: 13px; color: #e2e8f0; }
`;

// Extra rules for the PORTALED Load form. The form is mounted in its own host
// appended to document.body (see syncOverlay), so it escapes the widget's grid
// cell — react-grid-layout puts a `transform` on every cell, which would pin a
// `position: fixed` overlay to the cell instead of the viewport. Out here the
// `.modal` backdrop is fixed to the real viewport, so the form opens FULLPAGE.
const OVERLAY_STYLES = `
    .modal { position: fixed; z-index: 2147483000; }
    .modal-card.form-card { max-width: 680px; max-height: 90vh; overscroll-behavior: contain; }
    .form-card .form { max-width: none; overflow: visible; }
    .form-card header h3 { margin: 0 0 12px; font-size: 16px; color: #ffffff; }
`;

// The Scheda modal (click the plan) gets the SAME fullpage portal treatment: the
// `.modal` backdrop is fixed to the real viewport. The card holds the whole image —
// zoomable, in a scrollable frame — over the loaded characteristics laid out across
// the width (a grid, not one vertical column).
const MODAL_OVERLAY_STYLES = `
    .modal { position: fixed; z-index: 2147483000; }
    .modal-card.scheda-card { width: 100%; max-width: 1000px; max-height: 92vh; overscroll-behavior: contain; }
    .scheda-card .modal-head h3 { margin: 0; font-size: 16px; color: #ffffff; }
    /* Flex + "safe center" keeps the plan centred while it fits, but falls back to
       start-aligned (fully scrollable) once a zoom makes it overflow — so no part is
       ever clipped. "flex: none" lets the inline zoom width win. */
    .scheda-image-wrap { display: flex; justify-content: safe center; align-items: safe center;
                         overflow: auto; overscroll-behavior: contain; max-height: 62vh; margin: 12px 0 8px;
                         border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; background: rgba(0,0,0,0.25); }
    .scheda-image { display: block; height: auto; flex: none; }
    .zoom-bar { display: flex; gap: 6px; align-items: center; justify-content: center; margin-bottom: 12px; }
    .zoom-btn { padding: 4px 12px; border: 1px solid rgba(255,255,255,0.18); border-radius: 6px; background: rgba(255,255,255,0.05);
                color: #f9fafb; font: inherit; font-size: 14px; cursor: pointer; }
    .zoom-btn:hover { background: rgba(255,255,255,0.10); }
    .scheda-card .section { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8;
                            margin: 4px 0 8px; text-align: center; }
    .scheda-card .readout { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px 18px; }
    .scheda-card .readout .row { align-items: center; text-align: center; }
`;

class CharacteristicWidget extends HTMLElement {
    static get observedAttributes() {
        return ["token", "base"];
    }

    private root: ShadowRoot;
    private active?: ActiveWorkshop; // the current Active Workshop, from the bus (detail)
    private unsubscribe?: () => void; // bus teardown on disconnect

    // Last-loaded frame + interaction state. The Sezione image is fetched LAZILY,
    // only when a Sezione is picked (selectedId), so the list never drags every
    // plan upfront. imageUrl is an object URL we own and must revoke.
    private blueprints: BlueprintMeta[] = [];
    private scheda: Scheda | null = null; // the Bene's reuse data; null until first Load
    private selectedId?: number;
    private imageUrl?: string;
    private formOpen = false;
    private modalOpen = false; // the Scheda modal, opened by clicking the centre Blueprint
    private note?: string; // transient loading / error line for the WIDGET body
    private formNote?: string; // transient validation / save error, shown ONLY in the modal
    // The Load form's portal: a host appended to document.body so the form opens
    // fullpage (viewport), free of the widget's transformed grid cell. Created on
    // demand when the form opens, torn down when it closes / the widget unmounts.
    private overlay?: HTMLElement;
    private overlayRoot?: ShadowRoot;
    private prevBodyOverflow = ""; // body's overflow before we locked it, to restore
    // The Scheda modal's own fullpage portal (separate from the Load form's), with its
    // own scroll lock and a zoom level for the displayed plan.
    private modalOverlay?: HTMLElement;
    private modalOverlayRoot?: ShadowRoot;
    private prevBodyOverflowModal = "";
    private modalZoom = 1; // 1 = fit the frame's width; >1 enlarges (scroll to pan)
    // What the user typed but hasn't saved. Captured when the form is dismissed by
    // clicking the backdrop (and on every re-render) so reopening restores it in full
    // — every Planimetria row (Sezione text + chosen image) and the Scheda. Cleared
    // by Annulla, a successful Save, or switching Bene.
    private draft?: { rows: SezioneDraft[]; scheda: Scheda };

    constructor() {
        super();
        this.root = this.attachShadow({ mode: "open" });
        // One delegated listener for the whole shell — survives every re-render
        // (innerHTML replaces the markup, never the host element's listeners).
        this.root.addEventListener("click", (e) => this.onClick(e));
        // Picking a Sezione from the state-3 dropdown selects its plan.
        this.root.addEventListener("change", (e) => {
            const t = e.target;
            if (t instanceof HTMLSelectElement && t.classList.contains("sezioni-select")) {
                void this.selectSezione(Number(t.value));
            }
        });
    }

    connectedCallback() {
        // Converge however we join (ADR-0003): take the retained value at mount,
        // then react to every later selection. A null retained value renders idle.
        this.active = readActiveWorkshop();
        this.unsubscribe = subscribeActiveWorkshop((workshop) => {
            this.active = workshop;
            void this.refresh();
        });
        void this.refresh();
    }

    disconnectedCallback() {
        this.unsubscribe?.();
        this.unsubscribe = undefined;
        this.setImageUrl(undefined); // revoke any held object URL
        this.teardownOverlay(); // never leave a portal behind in document.body
        this.teardownSchedaModal();
    }

    attributeChangedCallback() {
        if (!this.isConnected) return;
        // A token arriving after mount (first login) lets the initial frame load;
        // a fresh base/token otherwise just re-renders against the current state.
        void this.refresh();
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

    // Reload the light Sezione listing for the Active Workshop and re-render. The
    // image is NOT fetched here — only when a Sezione is selected (lazy). A change
    // of Bene clears the prior selection and any held image.
    private async refresh() {
        const active = this.active;
        // A fresh Bene (or none): drop the previous Sezione selection + its image.
        this.selectedId = undefined;
        this.setImageUrl(undefined);
        this.formOpen = false;
        this.modalOpen = false;
        this.note = undefined;
        this.formNote = undefined; // close the modal cleanly on save/Bene change
        this.blueprints = [];
        this.scheda = null;
        this.draft = undefined; // a saved form or a new Bene discards any unsaved draft

        if (!active) {
            this.render();
            return;
        }
        if (!this.authToken) {
            // We have a Bene but no token yet: show its identity while we wait.
            this.note = "Caricamento…";
            this.render();
            return;
        }
        try {
            const frame = await this.api<WorkshopFrame>(`/characteristic/workshops/${active.poiId}`);
            // Guard against a selection that changed while the request was in flight.
            if (this.active?.poiId !== active.poiId) return;
            this.blueprints = frame.blueprints;
            this.scheda = frame.scheda;
            // State 3: make the first Sezione active immediately (it fetches its image
            // and renders); otherwise just render the empty state.
            if (this.blueprints.length > 0) {
                void this.selectSezione(this.blueprints[0].id);
            } else {
                this.render();
            }
        } catch {
            if (this.active?.poiId !== active.poiId) return;
            this.note = "Impossibile caricare la scheda.";
            this.render();
        }
    }

    // Hold exactly one object URL for the displayed image; revoke the previous so
    // selecting Sezione after Sezione never leaks blobs.
    private setImageUrl(url: string | undefined) {
        if (this.imageUrl && this.imageUrl !== url) URL.revokeObjectURL(this.imageUrl);
        this.imageUrl = url;
    }

    // Delegated click routing for the (re-rendered) shell: open/cancel the Load
    // form, submit an upload, or lazily fetch a Sezione's image.
    private onClick(e: Event) {
        const el = (e.target as HTMLElement)?.closest("[data-action], .sezione") as HTMLElement | null;
        if (!el) return;
        const action = el.dataset.action;
        if (action === "open-form") {
            this.formOpen = true;
            this.note = undefined;
            this.formNote = undefined; // a fresh form starts with no error line
            this.render();
        } else if (action === "dismiss") {
            // Click outside the card: close but keep the unsaved input for next time.
            this.snapshotDraft();
            this.formOpen = false;
            this.formNote = undefined; // the transient error doesn't outlive the modal
            this.render();
        } else if (action === "cancel") {
            // Annulla: an explicit abort, so the draft is discarded.
            this.draft = undefined;
            this.formOpen = false;
            this.formNote = undefined;
            this.render();
        } else if (action === "add-sezione") {
            this.addSezioneRow();
        } else if (action === "remove-sezione") {
            // In place (no re-render) so the other rows' chosen files survive.
            el.closest(".sezione-row")?.remove();
        } else if (action === "submit") {
            void this.submitUpload();
        } else if (action === "delete") {
            void this.deleteBlueprint(Number(el.dataset.id));
        } else if (action === "open-modal") {
            this.modalOpen = true;
            this.modalZoom = 1; // open showing the whole plan, fit to the frame width
            this.render();
        } else if (action === "close-modal") {
            this.modalOpen = false;
            this.render();
        } else if (action === "zoom-in") {
            this.setModalZoom(this.modalZoom * 1.25);
        } else if (action === "zoom-out") {
            this.setModalZoom(this.modalZoom / 1.25);
        } else if (action === "zoom-reset") {
            this.setModalZoom(1);
        } else if (el.classList.contains("sezione")) {
            void this.selectSezione(Number(el.dataset.id));
        }
    }

    // LAZY image fetch: runs only on a Sezione click, fetching that one Blueprint's
    // bytes by id. The light listing never pulls bytes, so plans load one at a time,
    // on demand — never all upfront.
    private async selectSezione(id: number) {
        if (!Number.isFinite(id)) return;
        this.selectedId = id;
        this.setImageUrl(undefined);
        this.note = "Caricamento planimetria…";
        this.render();
        try {
            const res = await fetch(`${this.baseUrl}/characteristic/blueprints/${id}`, {
                headers: this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {},
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const blob = await res.blob();
            if (this.selectedId !== id) return; // a newer selection won the race
            this.setImageUrl(URL.createObjectURL(blob));
            this.note = undefined;
            this.render();
        } catch {
            if (this.selectedId !== id) return;
            this.note = "Impossibile caricare la planimetria.";
            this.render();
        }
    }

    // Remove the shown Sezione's Blueprint via the write-guarded DELETE route so a
    // Master can correct a mistaken upload. On success we re-list: the Sezione drops
    // out of the toggle-list and, if it was the LAST one, the empty list re-renders
    // as state 2 (the central Load button) — no separate branch needed.
    private async deleteBlueprint(id: number) {
        if (!Number.isFinite(id)) return;
        this.note = "Rimozione…";
        this.render();
        try {
            const res = await fetch(`${this.baseUrl}/characteristic/blueprints/${id}`, {
                method: "DELETE",
                headers: this.authToken ? { Authorization: `Bearer ${this.authToken}` } : {},
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            await this.refresh(); // re-list; the Sezione is gone (state 3 -> 2 if last)
        } catch {
            this.note = "Rimozione non riuscita. Riprova.";
            this.render();
        }
    }

    // Append an empty Planimetria row (Sezione + image) when "+" is clicked, in place
    // (no re-render) so the files already chosen in the other rows survive. Focus the
    // new Sezione so the user can type straight away.
    private addSezioneRow() {
        const list = this.overlayRoot?.querySelector("[data-sezioni]");
        if (!list) return;
        const tmp = document.createElement("template");
        tmp.innerHTML = sezioneRow("", true); // appended rows are removable
        const row = tmp.content.firstElementChild;
        if (!row) return;
        list.appendChild(row);
        row.querySelector<HTMLInputElement>("input[name=sezione]")?.focus();
    }

    // Submit the Load form: the Scheda (create-then-edit) folded with any Blueprint
    // uploads. Each COMPLETE Planimetria row (Sezione + image) is uploaded; a row
    // half-filled with only one of the two blocks the save; an empty row is ignored.
    //
    // Whether a Planimetria is REQUIRED depends on the mode: a first Load (the Bene
    // has no plans yet) needs at least one complete Sezione, but EDITING (the Bene
    // already has plans — opened via "Modifica") may save with no new Sezione at all,
    // so the Scheda alone can be corrected without re-uploading an image.
    private async submitUpload() {
        const active = this.active;
        if (!active) return;

        const scheda = this.readSchedaPayload();
        const rows = Array.from(this.formScope.querySelectorAll<HTMLElement>(".sezione-row")).map(
            (rowEl) => ({
                file: rowEl.querySelector<HTMLInputElement>("input[type=file]")?.files?.[0] ?? null,
                sezione: rowEl.querySelector<HTMLInputElement>("input[name=sezione]")?.value.trim() ?? "",
            }),
        );
        const uploads: { sezione: string; file: File }[] = [];
        for (const r of rows) {
            if (r.sezione && r.file) {
                uploads.push({ sezione: r.sezione, file: r.file });
                continue;
            }
            if (r.sezione || r.file) {
                // Partially filled (only a name or only an image) — never half-saved.
                this.formNote =
                    "Compila nome e immagine per ogni sezione della planimetria (o rimuovi le righe vuote) prima di salvare.";
                this.render();
                return;
            }
            // Both empty: skipped (allowed in edit mode for a Scheda-only save).
        }
        const editing = this.blueprints.length > 0; // the Bene already has plans
        if (uploads.length === 0) {
            if (!editing) {
                this.formNote = "Aggiungi almeno una sezione di planimetria con nome e immagine.";
                this.render();
                return;
            }
            if (isSchedaEmpty(scheda)) {
                this.formNote = "Modifica la scheda o aggiungi una sezione di planimetria.";
                this.render();
                return;
            }
        }

        const auth: Record<string, string> = this.authToken
            ? { Authorization: `Bearer ${this.authToken}` }
            : {};
        try {
            // 1) Save the Scheda ONLY when it carries data. A Planimetria-only save
            // (Sezione + image, nothing in the Scheda) skips this entirely — the
            // upload below auto-registers the Workshop — so an empty Scheda is never
            // required and no empty Scheda row is created.
            if (!isSchedaEmpty(scheda)) {
                const schedaRes = await fetch(`${this.baseUrl}/characteristic/scheda/${active.poiId}`, {
                    method: "PUT",
                    headers: { ...auth, "Content-Type": "application/json" },
                    body: JSON.stringify(scheda),
                });
                if (!schedaRes.ok) throw new Error(await errorDetail(schedaRes));
            }

            // 2) Upload each chosen Blueprint (one POST per Sezione row).
            for (const { sezione, file } of uploads) {
                const body = new FormData();
                body.append("poi_id", String(active.poiId));
                body.append("sezione", sezione);
                body.append("file", file);
                // No explicit Content-Type: the browser sets the multipart boundary.
                const res = await fetch(`${this.baseUrl}/characteristic/blueprints`, {
                    method: "POST",
                    headers: auth,
                    body,
                });
                if (!res.ok) throw new Error(await errorDetail(res));
            }
            await this.refresh(); // re-list; the new Sezioni (and Scheda, if any) show
        } catch (err) {
            // Surface the backend's reason (e.g. a 415 "Unsupported image format …")
            // instead of a blanket failure, so the cause is actionable.
            const reason = err instanceof Error ? err.message : "";
            this.formNote = reason
                ? `Salvataggio non riuscito: ${reason}`
                : "Salvataggio non riuscito. Controlla i campi e riprova.";
            this.render();
        }
    }

    // Collect the Scheda fields from the (open) Load form into the PUT body: the
    // text/enum inputs by name + the checked `vincoli`. Empties are dropped by
    // buildSchedaPayload, so an untouched form posts a valid empty Scheda.
    //
    // titolo and vincoli fold in their "altro" free-text box: a titolo of "altro"
    // saves the box's text (so the meaningful value, not "altro", is stored), and a
    // checked Vincoli "altro" contributes its box's text as a custom member. When
    // "altro" isn't selected the box is ignored, so its text is never saved.
    private readSchedaPayload(): Scheda {
        const scope = this.formScope;
        const text: Record<string, string> = {};
        for (const { name } of SCHEDA_FIELDS) {
            const el = scope.querySelector<HTMLInputElement | HTMLSelectElement>(`[name="${name}"]`);
            if (el) text[name] = el.value;
        }
        // titolo: the custom box replaces "altro" with its text (empty ⇒ dropped).
        if (text.titolo === "altro") {
            text.titolo =
                scope.querySelector<HTMLInputElement>('input[name="titolo_altro"]')?.value.trim() ?? "";
        }
        // vincoli: checked suggestions, with "altro" swapped for its box's text.
        const checked = Array.from(
            scope.querySelectorAll<HTMLInputElement>('input[name="vincoli"]:checked'),
        ).map((c) => c.value);
        const vincoli = checked.filter((v) => v !== "altro");
        if (checked.includes("altro")) {
            const custom =
                scope.querySelector<HTMLInputElement>('input[name="vincoli_altro"]')?.value.trim() ?? "";
            vincoli.push(custom !== "" ? custom : "altro");
        }
        return buildSchedaPayload(text, vincoli);
    }

    // Where the open Load form's inputs live: the portal root while the fullpage
    // form is mounted, the widget's own root otherwise. Keeps submitUpload and
    // readSchedaPayload reading from wherever the form was actually rendered.
    private get formScope(): ParentNode {
        return this.formOpen ? (this.overlayRoot ?? this.root) : this.root;
    }

    // Render the current state. State 1 (no Active Workshop) is the idle frame;
    // States 2 & 3 show the Bene's identity (from the bus detail, never re-stored)
    // plus either the central Load button (0 Blueprints) or the Sezioni toggle-list
    // with the lazily-loaded image in the centre (≥1 Blueprint). The Load form
    // overlays the centre when open.
    private render() {
        const active = this.active;
        if (!active) {
            this.root.innerHTML = `
                <style>${STYLES}</style>
                <div class="wrap">
                    <div class="body">
                        <div class="state">
                            <div>Seleziona un Bene per gestire schede e planimetrie.</div>
                            <button type="button" class="load faded" disabled style="margin-top:12px;">Load</button>
                        </div>
                    </div>
                </div>
            `;
            this.syncOverlay();
            this.syncSchedaModal();
            return;
        }

        const coords = `${active.lat.toFixed(5)}, ${active.lng.toFixed(5)}`;
        const hasBlueprints = this.blueprints.length > 0; // state 3
        this.root.innerHTML = `
            <style>${STYLES}</style>
            <div class="wrap">
                <header class="${hasBlueprints ? "bar" : ""}">
                    ${hasBlueprints ? `<div class="bar-side left">${this.renderControls()}</div>` : ""}
                    <div class="bar-center">
                        <div class="subtitle">${escapeHtml(active.name)}</div>
                        <div class="coords">${coords}</div>
                    </div>
                    ${hasBlueprints ? `<div class="bar-side right">${this.renderSezioniSelect()}</div>` : ""}
                </header>
                <div class="body">${this.renderBody()}</div>
            </div>
        `;
        // Neither the Load form NOR the Scheda modal is in this markup — both live in
        // fullpage portals on document.body.
        this.syncOverlay();
        this.syncSchedaModal();
    }

    // State 3's left-hand controls, raised into the header bar: Modifica then Rimuovi,
    // side by side. In state 3 the form EDITS what's already there (the button reads
    // "Modifica", not "Load"). Rimuovi targets the currently selected Sezione (always
    // set once the first Sezione auto-loads).
    private renderControls(): string {
        const remove = this.selectedId
            ? `<button type="button" class="load small remove" data-action="delete" data-id="${this.selectedId}">Rimuovi</button>`
            : "";
        return `<button type="button" class="load small" data-action="open-form">Modifica</button>${remove}`;
    }

    // State 3's right-hand control: the Sezioni as a dropdown (the selected one is the
    // shown image). Replaces the old toggle-button column; black option text so a
    // white native popup stays readable.
    private renderSezioniSelect(): string {
        const options = this.blueprints
            .map(
                (b) =>
                    `<option value="${b.id}"${b.id === this.selectedId ? " selected" : ""}>${escapeHtml(b.sezione)}</option>`,
            )
            .join("");
        return `<select class="sezioni-select" aria-label="Sezione planimetria">${options}</select>`;
    }

    // The centre of an active frame: the Load form when open, else state 2 (central
    // Load button) or state 3 (Sezioni list + small Load + the selected image).
    private renderBody(): string {
        // The Load form opens fullpage in a portal (syncOverlay), so it no longer
        // overlays the centre here; the underlying state stays put beneath it.
        if (this.blueprints.length === 0) {
            const note = this.note ? `<div class="state">${escapeHtml(this.note)}</div>` : "";
            return `${note}<button type="button" class="load primary" data-action="open-form">Load</button>`;
        }

        // State 3: the Load/Rimuovi buttons and the Sezione dropdown live in the header
        // bar now, so the body is just the selected plan (or its loading/placeholder
        // line) — giving the image the full body height.
        if (this.note) return `<div class="state">${escapeHtml(this.note)}</div>`;
        if (this.imageUrl)
            return `<img class="image" src="${this.imageUrl}" alt="Planimetria" title="Apri la scheda di riuso" data-action="open-modal" />`;
        return `<div class="placeholder">Seleziona una Sezione</div>`;
    }

    // The Load form: the optional Blueprint (image + Sezione) folded with the Scheda
    // fields. On the FIRST Load the Scheda fields are blank (it is being created); on
    // a LATER Load they are PRE-FILLED from the saved Scheda and editable, so it is
    // never re-entered from scratch. All Scheda fields are optional/non-blocking.
    private renderForm(): string {
        const note = this.formNote ? `<div class="state error">${escapeHtml(this.formNote)}</div>` : "";
        // Restore an unsaved draft (dismissed by clicking outside) when present;
        // otherwise pre-fill from the saved Scheda. The Planimetria rows live only in
        // the draft (the saved Scheda has none); the chosen images are re-attached
        // after this markup is mounted (restoreSezioneFiles).
        const s = this.draft?.scheda ?? this.scheda ?? {};
        const rows = this.draft?.rows?.length ? this.draft.rows : [{ sezione: "", file: null }];
        const sezioniRows = rows.map((r, i) => sezioneRow(r.sezione, i > 0)).join("");
        // titolo is a <select> with an "altro" free-text box (titoloField); Vincoli is
        // a checkbox group with its own "altro" box (vincoliField). Picking/checking
        // "altro" reveals the box; deselecting hides it and discards the text. Estremi
        // and Note sui vincoli are always free text.
        const titoloVal = (s.titolo as string) ?? "";
        const vincoliVal = s.vincoli ?? [];
        // vincoli_note is rendered below the Vincoli group, not inline in the grid.
        const schedaFields = SCHEDA_FIELDS.filter(({ name }) => name !== "vincoli_note")
            .map(({ name, label, enum: values }) => {
                if (name === "titolo") return titoloField(label, titoloVal);
                if (values) return selectField(name, label, values, (s[name] as string) ?? "");
                return textField(name, label, (s[name] as string) ?? "");
            })
            .join("");
        const vincoli = vincoliField(vincoliVal);
        const vincoliNote = textField("vincoli_note", "Note sui vincoli", (s.vincoli_note as string) ?? "");
        return `
            <div class="form">
                ${note}
                <div class="section">Planimetria</div>
                <div class="sezioni-list" data-sezioni>
                    ${sezioniRows}
                </div>
                <button type="button" class="load add" data-action="add-sezione">+ Aggiungi sezione</button>
                <div class="section">Scheda di riuso</div>
                <div class="grid2">
                    ${schedaFields}
                </div>
                ${vincoli}
                ${vincoliNote}
                <div class="actions">
                    <button type="button" class="load ghost" data-action="cancel">Annulla</button>
                    <button type="button" class="load" data-action="submit">Salva</button>
                </div>
            </div>
        `;
    }

    // Mount/refresh/tear down the fullpage Load form in a portal on document.body.
    // The portal escapes the widget's transformed grid cell, so the `.modal`
    // backdrop is fixed to the real viewport (fullpage) rather than the cell. It
    // carries its own click listener and its inputs are read via `formScope`.
    private syncOverlay() {
        if (!this.formOpen) {
            this.teardownOverlay();
            return;
        }
        if (!this.overlay) {
            // First open: mount the portal and lock the background so scrolling the
            // modal to its end never scrolls the page behind it.
            this.overlay = document.createElement("div");
            this.overlayRoot = this.overlay.attachShadow({ mode: "open" });
            this.overlayRoot.addEventListener("click", (e) => this.onClick(e));
            // Live "altro" toggling: enable/disable the companion text box as the
            // controlling titolo dropdown / Vincoli checkboxes change, no re-render.
            this.overlayRoot.addEventListener("change", (e) => this.onFormChange(e));
            this.prevBodyOverflow = document.body.style.overflow;
            document.body.style.overflow = "hidden";
            document.body.appendChild(this.overlay);
        } else {
            // A re-render of an already-open form (e.g. a validation note): keep the
            // input the user has typed so far so it isn't wiped by the rebuild.
            this.snapshotDraft();
        }
        // Backdrop carries data-action="dismiss": clicking outside the card closes
        // the form but preserves the draft (snapshotted above / on dismiss). Clicks
        // inside the card (data-action="noop") never close it.
        this.overlayRoot!.innerHTML = `
            <style>${STYLES}${OVERLAY_STYLES}</style>
            <div class="modal" data-action="dismiss">
                <div class="modal-card form-card" data-action="noop">
                    <header><h3>${this.blueprints.length > 0 ? "Modifica" : "Load"}</h3></header>
                    ${this.renderForm()}
                </div>
            </div>
        `;
        // File inputs can't be valued via markup, so re-attach each row's chosen
        // image (from the draft) now that the rows exist in the DOM.
        this.restoreSezioneFiles();
    }

    // The "altro" rule, applied live: selecting "altro" in the titolo dropdown, or
    // checking it in Vincoli, reveals that control's free-text box (focused, ready to
    // type); any other choice hides the box and CLEARS it, so a deselected "altro"
    // detail is discarded and never saved. Direct DOM toggling (no re-render) keeps
    // every other field's input intact.
    private onFormChange(e: Event) {
        const target = e.target as HTMLElement | null;
        const root = this.overlayRoot;
        if (!root || !target) return;
        if (target instanceof HTMLSelectElement && target.name === "titolo") {
            this.toggleAltroBox("titolo_altro", target.value === "altro");
        } else if (
            target instanceof HTMLInputElement &&
            target.name === "vincoli" &&
            target.value === "altro"
        ) {
            this.toggleAltroBox("vincoli_altro", target.checked);
        }
    }

    // Show + focus an "altro" free-text box, or hide and clear it (discarding the
    // text) when its "altro" option is turned off.
    private toggleAltroBox(name: string, show: boolean) {
        const box = this.overlayRoot?.querySelector<HTMLInputElement>(`input[name="${name}"]`);
        if (!box) return;
        box.hidden = !show;
        if (show) box.focus();
        else box.value = "";
    }

    // Capture the form's current values so a dismissed or re-rendered form can be
    // restored in full: every Planimetria row (Sezione text + chosen File) plus the
    // Scheda. The File is held in memory and re-attached on reopen (restoreSezioneFiles).
    private snapshotDraft() {
        if (!this.overlayRoot) return;
        const rows: SezioneDraft[] = Array.from(
            this.overlayRoot.querySelectorAll<HTMLElement>(".sezione-row"),
        ).map((rowEl) => ({
            sezione: rowEl.querySelector<HTMLInputElement>('input[name="sezione"]')?.value ?? "",
            file: rowEl.querySelector<HTMLInputElement>('input[type="file"]')?.files?.[0] ?? null,
        }));
        this.draft = { rows, scheda: this.readSchedaPayload() };
    }

    // Re-attach each draft row's chosen image to its file input. Markup can't carry a
    // file value, but `input.files` can be set from a DataTransfer — so the image
    // survives a dismiss/reopen (and any re-render) alongside the Sezione text.
    private restoreSezioneFiles() {
        const rows = this.draft?.rows;
        if (!rows || !this.overlayRoot) return;
        const rowEls = this.overlayRoot.querySelectorAll<HTMLElement>(".sezione-row");
        rows.forEach((r, i) => {
            if (!r.file) return;
            const input = rowEls[i]?.querySelector<HTMLInputElement>('input[type="file"]');
            if (!input) return;
            const dt = new DataTransfer();
            dt.items.add(r.file);
            input.files = dt.files;
        });
    }

    private teardownOverlay() {
        if (!this.overlay) return;
        this.overlay.remove();
        this.overlay = undefined;
        this.overlayRoot = undefined;
        document.body.style.overflow = this.prevBodyOverflow; // unlock the page
    }

    // Mount/refresh/tear down the fullpage Scheda modal in its own portal on
    // document.body — escaping the transformed grid cell just like the Load form — and
    // lock the background scroll while it is open.
    private syncSchedaModal() {
        if (!this.modalOpen) {
            this.teardownSchedaModal();
            return;
        }
        if (!this.modalOverlay) {
            this.modalOverlay = document.createElement("div");
            this.modalOverlayRoot = this.modalOverlay.attachShadow({ mode: "open" });
            this.modalOverlayRoot.addEventListener("click", (e) => this.onClick(e));
            this.prevBodyOverflowModal = document.body.style.overflow;
            document.body.style.overflow = "hidden";
            document.body.appendChild(this.modalOverlay);
        }
        this.modalOverlayRoot!.innerHTML = `
            <style>${STYLES}${MODAL_OVERLAY_STYLES}</style>
            ${this.renderModal()}
        `;
    }

    private teardownSchedaModal() {
        if (!this.modalOverlay) return;
        this.modalOverlay.remove();
        this.modalOverlay = undefined;
        this.modalOverlayRoot = undefined;
        document.body.style.overflow = this.prevBodyOverflowModal;
    }

    // Clamp the zoom and apply it straight to the displayed image (no re-render, so
    // the scroll position and the open modal are untouched). 1 = fit the frame width.
    private setModalZoom(zoom: number) {
        this.modalZoom = Math.min(5, Math.max(0.25, zoom));
        const img = this.modalOverlayRoot?.querySelector<HTMLImageElement>(".scheda-image");
        if (img) img.style.width = `${this.modalZoom * 100}%`;
    }

    // The fullpage Scheda modal, opened by clicking the plan: the whole image up top —
    // zoomable in a scrollable frame — over the loaded characteristics laid out across
    // the width. The backdrop (data-action="close-modal") closes it; clicks inside the
    // card (data-action="noop") do not. State 4: an empty Scheda reads "non disponibile".
    private renderModal(): string {
        const image = this.imageUrl
            ? `<div class="scheda-image-wrap">
                   <img class="scheda-image" src="${this.imageUrl}" alt="Planimetria" style="width:${this.modalZoom * 100}%" />
               </div>
               <div class="zoom-bar">
                   <button type="button" class="zoom-btn" data-action="zoom-out" aria-label="Riduci">−</button>
                   <button type="button" class="zoom-btn" data-action="zoom-reset">Adatta</button>
                   <button type="button" class="zoom-btn" data-action="zoom-in" aria-label="Ingrandisci">+</button>
               </div>`
            : "";
        const readout = isSchedaEmpty(this.scheda)
            ? `<div class="state">Scheda non disponibile</div>`
            : renderSchedaReadout(this.scheda as Scheda);
        return `
            <div class="modal" data-action="close-modal">
                <div class="modal-card scheda-card" data-action="noop">
                    <header class="modal-head">
                        <h3>Scheda di riuso</h3>
                    </header>
                    ${image}
                    <div class="section">Caratteristiche</div>
                    ${readout}
                </div>
            </div>
        `;
    }
}

// Pull the backend's error reason from a non-OK response: FastAPI puts it in
// ``{detail: "…"}``. Falls back to the bare status so the caller always has a string.
async function errorDetail(res: Response): Promise<string> {
    try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body?.detail === "string") return body.detail;
    } catch {
        /* non-JSON / empty body — fall through to the status line */
    }
    return `HTTP ${res.status}`;
}

// One Planimetria row: a Sezione label + its loadable image. The Load form starts
// with one and the "+" button appends more (addSezioneRow), so several Sezioni can
// be uploaded in a single save. Appended rows carry a "×" to remove them again; the
// first row has none (there is always at least one). The chosen image is restored on
// reopen by re-attaching the File via DataTransfer (restoreSezioneFiles).
function sezioneRow(sezione: string, removable: boolean): string {
    const remove = removable
        ? `<button type="button" class="row-remove" data-action="remove-sezione" aria-label="Rimuovi sezione" title="Rimuovi sezione">×</button>`
        : "";
    return `<div class="sezione-row">
        <div class="grid2">
            <label>Sezione
                <input type="text" name="sezione" value="${escapeHtml(sezione)}" placeholder="es. Piano terra" />
            </label>
            <label>Immagine
                <input type="file" accept="image/png,image/jpeg,image/webp,image/avif" />
            </label>
        </div>
        ${remove}
    </div>`;
}

// One labelled free-text input, pre-filled with the saved value (escaped).
function textField(name: string, label: string, current: string): string {
    return `<label>${escapeHtml(label)}
        <input type="text" name="${name}" value="${escapeHtml(current)}" />
    </label>`;
}

// One labelled dropdown over an enum-like field's allowed values, with a blank
// first option (the field is optional) and the saved value pre-selected.
function selectField(name: string, label: string, values: readonly string[], current: string): string {
    const options = [`<option value=""></option>`]
        .concat(
            values.map(
                (v) => `<option value="${v}"${v === current ? " selected" : ""}>${escapeHtml(v)}</option>`,
            ),
        )
        .join("");
    return `<label>${escapeHtml(label)}<select name="${name}">${options}</select></label>`;
}

// The titolo dropdown's suggested values minus "altro".
const KNOWN_TITOLO = TITOLO_VALUES.filter((v) => v !== "altro");

// titolo as an always-present <select>; choosing "altro" reveals a free-text box
// below it (titolo_altro) to type a custom value. A SAVED value outside the
// suggested set is a custom "altro": the select shows "altro" and the box carries
// the text. Deselecting "altro" hides the box and discards its text (onFormChange
// clears it; readSchedaPayload only reads it while "altro" is selected).
function titoloField(label: string, value: string): string {
    const known = KNOWN_TITOLO.includes(value as (typeof KNOWN_TITOLO)[number]);
    const selectValue = known ? value : value === "" ? "" : "altro";
    const isAltro = selectValue === "altro";
    const altroText = isAltro && value !== "altro" ? value : "";
    const options = [`<option value=""></option>`]
        .concat(
            TITOLO_VALUES.map(
                (v) => `<option value="${v}"${v === selectValue ? " selected" : ""}>${escapeHtml(v)}</option>`,
            ),
        )
        .join("");
    return `<label>${escapeHtml(label)}
        <select name="titolo">${options}</select>
        <input type="text" name="titolo_altro" class="altro" value="${escapeHtml(altroText)}" placeholder="Specifica «altro»"${isAltro ? "" : " hidden"} />
    </label>`;
}

// The multi-valued `vincoli` as a checkbox group. A SAVED member outside the
// suggested set is a custom "altro": "altro" is checked and the free-text box below
// (vincoli_altro) carries the text. Checking/clearing "altro" reveals/hides the box,
// discarding its text when unchecked (onFormChange / readSchedaPayload mirror this).
function vincoliField(current: string[]): string {
    const customMembers = current.filter(
        (v) => !VINCOLI_VALUES.includes(v as (typeof VINCOLI_VALUES)[number]),
    );
    const altroChecked = customMembers.length > 0 || current.includes("altro");
    const altroText = customMembers.join(", ");
    const boxes = VINCOLI_VALUES.map((v) => {
        const checked = v === "altro" ? altroChecked : current.includes(v);
        return `<label class="check"><input type="checkbox" name="vincoli" value="${v}"${
            checked ? " checked" : ""
        } /> ${escapeHtml(v)}</label>`;
    }).join("");
    return `<fieldset class="vincoli"><legend>Vincoli</legend>${boxes}
        <input type="text" name="vincoli_altro" class="altro" value="${escapeHtml(altroText)}" placeholder="Specifica «altro»"${altroChecked ? "" : " hidden"} />
    </fieldset>`;
}

// The modal read-out: only the FILLED Scheda fields, each as a label/value row, so
// the modal shows the reuse data in context without empty noise.
function renderSchedaReadout(scheda: Scheda): string {
    const rows: string[] = [];
    for (const { name, label } of SCHEDA_FIELDS) {
        const value = (scheda[name] as string | undefined)?.trim();
        if (value) rows.push(row(label, value));
    }
    if (scheda.vincoli && scheda.vincoli.length > 0) {
        rows.push(row("Vincoli", scheda.vincoli.join(", ")));
    }
    return `<div class="readout">${rows.join("")}</div>`;
}

function row(label: string, value: string): string {
    return `<div class="row"><span class="k">${escapeHtml(label)}</span><span class="v">${escapeHtml(value)}</span></div>`;
}

function escapeHtml(s: string): string {
    return s.replace(
        /[&<>"']/g,
        (c) =>
            ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c] as string,
    );
}

if (!customElements.get("characteristic-widget")) {
    customElements.define("characteristic-widget", CharacteristicWidget);
}
