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
    radar: { role: string; consensus: number }[];
    overall: number;
    n: number;
}

export interface RoundView {
    poi_id: number;
    phase: "lobby" | "voting" | "recap";
    round_number: number;
    ready_count: number;
    n: number;
    voted_count: number;
    remaining_count: number;
    voted_user_ids: string[];
    participants: RoundParticipant[];
    recap: RecapPayload | null;
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

/** The minimal socket surface RoundClient drives (the real WebSocket satisfies it). */
interface Sendable {
    send(data: string): void;
}

/** Sends the typed action messages; the room applies them under the handshake
 *  identity (the client never sends a user_id — the server owns it). */
export class RoundClient {
    private readonly socket: Sendable;

    constructor(socket: Sendable) {
        this.socket = socket;
    }

    join(): void {
        this.send({ type: "join" });
    }

    declareRole(role: string): void {
        this.send({ type: "declare_role", role });
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

    private send(message: object): void {
        this.socket.send(JSON.stringify(message));
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
    socket.addEventListener("message", (event) => {
        const message = parseServerMessage(String((event as MessageEvent).data));
        if (message.kind === "view") {
            onView(message.view);
        } else {
            onError(message.detail);
        }
    });
    return { client: new RoundClient(socket), close: () => socket.close() };
}
