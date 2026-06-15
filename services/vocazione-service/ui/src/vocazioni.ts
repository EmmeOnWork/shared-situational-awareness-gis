/**
 * The 16 Vocazioni — the closed catalog of target reuse archetypes from
 * Elenco_Funzioni.pdf, held as an in-bundle constant (this Widget owns no tables
 * and calls no data route; the list ships inside the bundle).
 *
 * Each entry is `{ id, label }`:
 *   - `label` = the short Denominazione (the name before the "–"/":"/"-" in the PDF,
 *     e.g. "Dimora del Benessere"). Shown in the dropdown; safe to reword.
 *   - `id` = a stable kebab slug derived from the label (accents/apostrophes stripped),
 *     e.g. "dimora-del-benessere". CONSUMERS KEY OFF THIS, never the label — it is the
 *     stable identifier that survives a relabel and rides the bus / the URL.
 * The rich PDF text (descrizione / attività / spazi) is deliberately NOT included.
 */

/** One Vocazione: the value carried on the `vocazione` selection axis. */
export interface Vocazione {
    id: string;
    label: string;
}

/** The 16 fixed Vocazioni, in the PDF's order (Rif. 1–16). */
export const VOCAZIONI: readonly Vocazione[] = [
    { id: "dimora-del-benessere", label: "Dimora del Benessere" },
    { id: "atelier-di-ricordi", label: "Atelier di Ricordi" },
    { id: "incubatore-rurale-di-comunita", label: "Incubatore Rurale di Comunità" },
    { id: "re-star-borgo", label: "Re-Star Borgo" },
    { id: "ostello-rurale-di-comunita", label: "Ostello Rurale di Comunità" },
    { id: "rural-futures", label: "Rural Futures" },
    { id: "botteghe-intergenerazionali", label: "Botteghe Intergenerazionali" },
    { id: "borgo-lab", label: "Borgo Lab" },
    { id: "radici-visive", label: "Radici Visive" },
    { id: "accoglienza-educativa", label: "Accoglienza Educativa" },
    { id: "presidio-medico-integrato", label: "Presidio Medico Integrato" },
    {
        id: "hub-dei-servizi-di-prossimita-e-dei-diritti",
        label: "Hub dei Servizi di Prossimità e dei Diritti",
    },
    {
        id: "laboratorio-di-economia-circolare-e-filiere-locali",
        label: "Laboratorio di Economia Circolare e Filiere Locali",
    },
    {
        id: "hub-della-mobilita-rurale-lenta-e-condivisa",
        label: "Hub della Mobilità Rurale, Lenta e Condivisa",
    },
    {
        id: "osservatorio-territoriale-e-centro-dati-di-comunita",
        label: "Osservatorio Territoriale e Centro Dati di Comunità",
    },
    {
        id: "presidio-di-comunita-per-la-resilienza-e-la-protezione-civile",
        label: "Presidio di Comunità per la Resilienza e la Protezione Civile",
    },
];

/** Resolve a slug to its Vocazione, or `undefined` for an unknown/stale slug. */
export function findVocazione(id: string): Vocazione | undefined {
    return VOCAZIONI.find((v) => v.id === id);
}
