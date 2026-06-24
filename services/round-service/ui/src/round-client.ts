/**
 * The round WS client — the realtime transport half of <round-widget>.
 *
 * Opens one WebSocket to the Bene's room (`/rounds/ws/{poiId}`) through the edge
 * gateway, carrying the host's JWT on the handshake via the `access_token`
 * subprotocol pair (a browser cannot set an Authorization header on a WS upgrade).
 * Inbound frames are either a full view (the room's state) or an error addressed to
 * this client; outbound, each user action is one small typed message the
 * RoomManager maps to an engine event. Pure helpers (parse + URL) are unit-tested;
 * the socket lifecycle is thin glue.
 */

export interface RoundParticipant {
    user_id: string;
    role: string | null;
    ready: boolean;
}

export interface RecapPayload {
    radar: { role: string; consensus: number; count: number }[];
    overall: number;
    n: number;
}

/** One anonymous Chat message as the room broadcasts it: NO author, just the Round
 *  it was posted in, the body and an ISO timestamp. Present only when this client
 *  may read the Chat (after it has voted, or in the recap); empty otherwise. */
export interface ChatMessage {
    round_number: number;
    body: string;
    timestamp: string;
}

export interface RoundView {
    poi_id: number;
    phase: "lobby" | "voting" | "recap" | "consensus";
    round_number: number;
    ready_count: number;
    n: number;
    voted_count: number;
    remaining_count: number;
    voted_user_ids: string[];
    participants: RoundParticipant[];
    recap: RecapPayload | null;
    // The terminal phase-4 payload (present only when phase === "consensus"): the
    // winning Vocazione the group converged on and how many Rounds it took.
    consensus: { winner: string; rounds: number } | null;
    chat: ChatMessage[];
}

export type ServerMessage =
    | { kind: "view"; view: RoundView }
    | { kind: "error"; detail: string };

/** The subprotocol that flags the next protocol value as the bearer token. */
export const TOKEN_SUBPROTOCOL = "access_token";

/** Classify an inbound frame: an error addressed to us, else a state view. */
export function parseServerMessage(data: string): ServerMessage {
    const parsed = JSON.parse(data);
    if (parsed && parsed.type === "error") {
        return { kind: "error", detail: String(parsed.detail) };
    }
    return { kind: "view", view: parsed as RoundView };
}

/** Build the room's WebSocket URL from the gateway base and the Bene id. */
export function roundSocketUrl(base: string, poiId: number): string {
    const origin = base || (typeof location !== "undefined" ? location.origin : "");
    const wsOrigin = origin.replace(/^http/, "ws");
    return `${wsOrigin}/rounds/ws/${poiId}`;
}

/** The WebSocket OPEN readyState (WebSocket.OPEN), named to avoid the magic 1. */
const WS_OPEN = 1;

/** The minimal socket surface RoundClient drives (the real WebSocket satisfies it).
 *  `readyState` is optional so tests can pass a bare `{ send }` (treated as ready). */
interface Sendable {
    send(data: string): void;
    readyState?: number;
}

/** Sends the typed action messages; the room applies them under the handshake
 *  identity (the client never sends a user_id — the server owns it). */
export class RoundClient {
    private readonly socket: Sendable;
    // Messages enqueued while the socket is still CONNECTING, flushed on `open`.
    private readonly pending: string[] = [];

    constructor(socket: Sendable) {
        this.socket = socket;
    }

    /** Join the Bene's process. The stakeholder Role is not sent — the server reads
     *  it from the handshake JWT (set at registration), so there is no declare step. */
    join(): void {
        this.send({ type: "join" });
    }

    ready(): void {
        this.send({ type: "ready" });
    }

    /** Open a Round through the ready-gate — the same message for Round 1 and for
     *  "inizia un nuovo round" in the recap. */
    start(): void {
        this.send({ type: "start" });
    }

    vote(vocazione: string): void {
        this.send({ type: "vote", vocazione });
    }

    /** Post one anonymous Chat message. The server gates it (rejected unless this
     *  user has already voted in the open Round) and fans the anonymised message
     *  back out to every eligible reader. */
    chat(body: string): void {
        this.send({ type: "chat", body });
    }

    /** Send any messages buffered while the socket was connecting. Call on `open`. */
    flush(): void {
        if (this.socket.readyState !== undefined && this.socket.readyState !== WS_OPEN) return;
        for (const data of this.pending.splice(0)) this.socket.send(data);
    }

    private send(message: object): void {
        const data = JSON.stringify(message);
        // A click can land before the handshake completes; raw `socket.send` then
        // throws and the action is lost. Buffer until OPEN instead. A test's bare
        // fake has no `readyState` (undefined) → treated as ready, sent immediately.
        if (this.socket.readyState === undefined || this.socket.readyState === WS_OPEN) {
            this.socket.send(data);
        } else {
            this.pending.push(data);
        }
    }
}

/** Open a live room connection. Returns the RoundClient plus a close() teardown.
 *  Kept thin (untested) over the unit-tested helpers above. */
export function connectRoom(
    base: string,
    poiId: number,
    token: string,
    onView: (view: RoundView) => void,
    onError: (detail: string) => void,
): { client: RoundClient; close: () => void } {
    const socket = new WebSocket(roundSocketUrl(base, poiId), [TOKEN_SUBPROTOCOL, token]);
    const client = new RoundClient(socket);
    // Deliver any action a user clicked before the handshake finished.
    socket.addEventListener("open", () => client.flush());
    socket.addEventListener("message", (event) => {
        const message = parseServerMessage(String((event as MessageEvent).data));
        if (message.kind === "view") {
            onView(message.view);
        } else {
            onError(message.detail);
        }
    });
    return { client, close: () => socket.close() };
}
