/**
 * The Scheda di Individuazione Immobile — the structured reuse data of a Bene, the
 * frontend mirror of the service's ``Scheda`` model. The Load form edits it and the
 * modal shows it; both lean on the two pure helpers here so the element stays thin.
 *
 * Identity (comune/coordinate) is deliberately NOT here — the POI is its source of
 * truth (decision A), shown from the Active Workshop bus, never re-entered here.
 */

/** The Scheda fields, all optional/non-blocking (a Blueprint may save with it empty). */
export interface Scheda {
    denominazione?: string;
    destinazione_uso?: string;
    titolo?: string;
    titolo_estremi?: string;
    stato_uso?: string;
    condizioni?: string;
    stato_descrizione?: string;
    vincoli?: string[];
    vincoli_note?: string;
    foglio?: string;
    particella?: string;
    referente_nome?: string;
    referente_email?: string;
    referente_tel?: string;
}

// The allowed values for the enum-like fields, mirroring the service's validation
// sets. Drive the form's dropdowns/checkboxes so the UI only ever offers values the
// backend will accept (it still validates — these are the same source of truth).
export const TITOLO_VALUES = ["proprieta", "comodato", "locazione", "altro"] as const;
export const STATO_USO_VALUES = ["in_uso", "parziale", "dismesso", "inutilizzato"] as const;
export const CONDIZIONI_VALUES = ["buone", "discrete", "scarse", "da_ristrutturare"] as const;
export const VINCOLI_VALUES = [
    "paesaggistico",
    "culturale",
    "urbanistico",
    "nessuno",
    "altro",
] as const;

/** The Scheda's free-text + enum fields, in form order. ``vincoli`` is handled
 *  separately (a checkbox group), so it is intentionally absent here. Drives both
 *  the Load form's inputs and the modal read-out, so the two never drift —
 *  ``destinazione_uso`` reads "(attuale)" to mark a building's current/legal use,
 *  distinct from a Vocazione's new possible use. */
export const SCHEDA_FIELDS: ReadonlyArray<{ name: keyof Scheda; label: string; enum?: readonly string[] }> = [
    { name: "denominazione", label: "Denominazione" },
    { name: "destinazione_uso", label: "Destinazione d'uso (attuale)" },
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

/**
 * State 4: a Scheda is "empty" when it was never filled (``null``) or every field is
 * blank / an empty array. The modal then shows "non disponibile" instead of blank
 * fields.
 */
export function isSchedaEmpty(scheda: Scheda | null | undefined): boolean {
    if (!scheda) return true;
    return Object.values(scheda).every((v) =>
        Array.isArray(v) ? v.length === 0 : (v ?? "").trim() === "",
    );
}

/**
 * Turn the raw Load-form values into the PUT body: trim text, DROP empty fields, and
 * include ``vincoli`` only when some are checked. An untouched form yields ``{}`` —
 * a valid empty Scheda — so a Blueprint can still be saved with the Scheda left
 * empty (optional/non-blocking). ``text`` holds the text/enum inputs by field name.
 */
export function buildSchedaPayload(text: Record<string, string>, vincoli: string[]): Scheda {
    const payload: Scheda = {};
    for (const [key, raw] of Object.entries(text)) {
        const value = (raw ?? "").trim();
        if (value !== "") (payload as Record<string, unknown>)[key] = value;
    }
    if (vincoli.length > 0) payload.vincoli = vincoli;
    return payload;
}
