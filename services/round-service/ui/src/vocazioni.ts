/**
 * The 16 Vocazioni — the closed catalog of target reuse archetypes, held as an
 * in-bundle constant (the same list the Vocazione Selector owns; CONTEXT.md says a
 * Vote picks from this *same* catalog). It is copied, not imported: each full-stack
 * Widget ships self-contained and shares no code (service ADR-0001).
 *
 * A Vote carries the stable `id` slug (consumers key off the id, never the label) —
 * here it is the ballot value sent to the round service, distinct from the Active
 * Vocazione filter the Selector publishes on the bus (same options, opposite axis).
 */

export interface Vocazione {
    id: string;
    label: string;
}

/** The 16 fixed Vocazioni, in the catalog's order (Rif. 1–16). */
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
