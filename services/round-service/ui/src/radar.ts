/**
 * Recap radar geometry — pure maths, no DOM (the SVG markup is built in the
 * element and covered by typecheck).
 *
 * One spoke per stakeholder Role present in the closed Round, evenly spaced around
 * a circle starting straight up and going clockwise. Each Role's data vertex sits
 * along its spoke at a distance proportional to that Role's intra-Role Consensus:
 * 0 → the centre (no cohesion), 1 → the rim (unanimous). The polygon through those
 * vertices is the radar; "consenso totale" is the pooled overall as a percent.
 */

export interface Branch {
    role: string;
    consensus: number;
}

export interface Point {
    x: number;
    y: number;
}

/** The data vertex for each branch, in input order (one per Role present). */
export function radarVertices(branches: Branch[], cx: number, cy: number, maxR: number): Point[] {
    const step = (2 * Math.PI) / branches.length;
    return branches.map((branch, i) => {
        // Start at the top (−90°) and go clockwise; scale the radius by consensus.
        const angle = -Math.PI / 2 + i * step;
        const r = maxR * branch.consensus;
        return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });
}

/** The rim endpoint of each spoke (the full-scale axis line ends), in input order. */
export function spokeEnds(count: number, cx: number, cy: number, maxR: number): Point[] {
    const step = (2 * Math.PI) / count;
    return Array.from({ length: count }, (_, i) => {
        const angle = -Math.PI / 2 + i * step;
        return { x: cx + maxR * Math.cos(angle), y: cy + maxR * Math.sin(angle) };
    });
}

/** Render the pooled overall Consensus as a whole-percent label ("61%"). */
export function consensoTotalePct(overall: number): string {
    return `${Math.round(overall * 100)}%`;
}
