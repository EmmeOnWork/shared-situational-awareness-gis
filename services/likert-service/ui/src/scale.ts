/**
 * Scala Likert gauge mapping — pure logic, no DOM (the SVG/markup is built in the
 * <likert-widget> element and covered by typecheck).
 *
 * A Gradimento value ∈ [1,5] maps LINEARLY to a needle position ∈ [0,1] (1★ →
 * left/red, 3★ → centre/yellow, 5★ → right/green). Five fixed buckets drive the
 * emoji + one-word Italian label; the bucket boundaries are half-open [lo, hi) so
 * each edge (1.8 / 2.6 / 3.4 / 4.2) belongs to the HIGHER bucket. A review count
 * below the FLOOR marks the answer low-confidence (the element fades the needle and
 * appends "pochi dati"). Labels are tunable; the bucket count is fixed at 5.
 */

/** Minimum pooled reviews for a confident Gradimento; below it → low-confidence. */
export const FLOOR = 15;

export interface Scale {
    /** Needle position along the gauge, 0 (left/red) … 1 (right/green). */
    position: number;
    /** A red→yellow→green colour at the needle, derived from the position. */
    color: string;
    /** The bucket emoji (😡🙁😐🙂😍). */
    emoji: string;
    /** The one-word Italian label for the bucket. */
    label: string;
    /** True when the pooled review count is below FLOOR (estimate, low trust). */
    lowConfidence: boolean;
}

interface Bucket {
    /** Inclusive lower bound; the bucket runs [min, next.min) (last is closed). */
    min: number;
    emoji: string;
    label: string;
}

// The five buckets, ascending. Each owns [min, nextMin); the last is closed at 5.
const BUCKETS: readonly Bucket[] = [
    { min: 1.0, emoji: "😡", label: "Per niente gradito" },
    { min: 1.8, emoji: "🙁", label: "Poco gradito" },
    { min: 2.6, emoji: "😐", label: "Nella media" },
    { min: 3.4, emoji: "🙂", label: "Gradito" },
    { min: 4.2, emoji: "😍", label: "Molto gradito" },
];

const clamp = (n: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, n));

/** Map a Gradimento `value` (1..5) and its pooled `totalReviews` to the gauge. */
export function toScale(value: number, totalReviews: number): Scale {
    const v = clamp(value, 1, 5);
    const position = (v - 1) / 4; // 1→0, 3→0.5, 5→1

    // The matching bucket is the last whose lower bound v has reached (half-open
    // boundaries → an edge value falls into the higher bucket).
    let bucket = BUCKETS[0];
    for (const b of BUCKETS) {
        if (v >= b.min) bucket = b;
    }

    return {
        position,
        color: colorAt(position),
        emoji: bucket.emoji,
        label: bucket.label,
        lowConfidence: totalReviews < FLOOR,
    };
}

/** Red (hue 0) at position 0 → green (hue 120) at position 1, yellow in the middle. */
function colorAt(position: number): string {
    const hue = Math.round(clamp(position, 0, 1) * 120);
    return `hsl(${hue}, 70%, 45%)`;
}
