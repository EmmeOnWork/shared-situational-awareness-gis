/**
 * The Notifier's audio core — severity → sound, plus the player that voices it.
 *
 * Mirrors Slice 2's notification.ts split: a DOM-free, unit-testable mapping
 * (`toneSequence`, the audio analogue of SEVERITY_COLOUR) that the host-coupled
 * glue (`NotifierAudio`) plays back verbatim. The player never branches on
 * severity — it just schedules whatever tones the pure map returns — so the
 * "audibly distinct / success celebratory" knowledge lives in one tested place.
 */

import type { Severity } from "./notification.ts";

/** One note in a severity's sound: a sine pitch, when it starts, how long it lasts. */
export interface Tone {
    freq: number; // Hz
    startMs: number; // offset from the start of the sequence
    durationMs: number;
}

/**
 * The sound a severity makes, as a pure sequence of tones — the audio analogue
 * of SEVERITY_COLOUR. `info` is a single bright ping; `warning` two urgent pulses
 * at one pitch; `success` an ascending four-note fanfare (the consensus-reached
 * case, audibly celebratory and clearly distinct from the other two). Pitched and
 * timed to carry — the brighter timbre + louder gain live in the player below.
 */
export function toneSequence(severity: Severity): Tone[] {
    return SEVERITY_TONES[severity];
}

const SEVERITY_TONES: Record<Severity, Tone[]> = {
    info: [{ freq: 784, startMs: 0, durationMs: 220 }], // G5 — one clear ping
    warning: [
        { freq: 600, startMs: 0, durationMs: 160 },
        { freq: 600, startMs: 190, durationMs: 160 },
    ],
    success: [
        { freq: 523, startMs: 0, durationMs: 150 }, // C5
        { freq: 659, startMs: 150, durationMs: 150 }, // E5
        { freq: 784, startMs: 300, durationMs: 150 }, // G5
        { freq: 1047, startMs: 450, durationMs: 260 }, // C6 — bright finish
    ],
};

// Peak gain of each note's envelope. Higher than a gentle chime so a Notification
// actually pulls the eye to the toast (the "attract more attention" tuning).
const PEAK_GAIN = 0.34;

/**
 * Voices a severity's `toneSequence` through Web Audio. HOST-COUPLED GLUE:
 * AudioContext + the autoplay-policy unlock are browser behaviour, verified
 * manually (PRD testing decisions, ADR-0004), not in node:test.
 *
 * Autoplay: browsers start the context `suspended` and only allow it to make
 * sound after a user gesture. We resume it on the FIRST page-wide `document`
 * click (once) — no visible "enable sound" control. A Notification arriving
 * before any gesture still toasts; its `play()` is a silent no-op (accepted
 * limitation), never a throw or a console-error storm.
 */
export class NotifierAudio {
    private ctx?: AudioContext;
    private readonly target: Document;

    constructor(target: Document = document) {
        this.target = target;
        // Lazily create the context on the first gesture so a page that never
        // notifies (or a non-browser test import) never touches Web Audio.
        this.target.addEventListener("click", () => this.unlock(), { once: true });
    }

    private unlock() {
        try {
            this.ctx ??= new AudioContext();
            void this.ctx.resume();
        } catch {
            // No Web Audio (or it is blocked): stay silent, keep toasting.
        }
    }

    /** Play the sound for `severity`; a silent no-op until the first gesture. */
    play(severity: Severity) {
        const ctx = this.ctx;
        if (!ctx || ctx.state !== "running") return;

        const now = ctx.currentTime;
        for (const tone of toneSequence(severity)) {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            // `triangle` over `sine`: a brighter, more present timbre that carries
            // and grabs attention without the harshness of a square/sawtooth buzz.
            osc.type = "triangle";
            osc.frequency.value = tone.freq;

            const startAt = now + tone.startMs / 1000;
            const endAt = startAt + tone.durationMs / 1000;
            // Short attack/release envelope so each note is a chime, not a click.
            gain.gain.setValueAtTime(0.0001, startAt);
            gain.gain.exponentialRampToValueAtTime(PEAK_GAIN, startAt + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.0001, endAt);

            osc.connect(gain).connect(ctx.destination);
            osc.start(startAt);
            osc.stop(endAt + 0.02);
        }
    }
}
