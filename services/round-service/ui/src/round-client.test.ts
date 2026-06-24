/**
 * Contract tests for the round WS client — the transport half of the widget.
 *
 * Zero-dependency (Node's built-in runner + a fake socket): the element's
 * rendering is covered by typecheck, but the message routing and the action
 * payloads it sends are pure logic worth pinning. They assert the server-message
 * parser (a view vs an error frame), the handshake URL builder, and that each
 * action sends exactly the message the RoomManager expects.
 */
import { test } from "node:test";
import assert from "node:assert/strict";

import {
    parseServerMessage,
    roundSocketUrl,
    RoundClient,
    type RoundView,
} from "./round-client.ts";

const LOBBY: RoundView = {
    poi_id: 42,
    phase: "lobby",
    round_number: 0,
    ready_count: 0,
    n: 0,
    voted_count: 0,
    remaining_count: 0,
    voted_user_ids: [],
    participants: [],
    recap: null,
    consensus: null,
    chat: [],
};

test("parseServerMessage reads a view frame", () => {
    const msg = parseServerMessage(JSON.stringify(LOBBY));

    assert.equal(msg.kind, "view");
    assert.equal(msg.kind === "view" && msg.view.phase, "lobby");
});

test("parseServerMessage reads an error frame", () => {
    const msg = parseServerMessage(JSON.stringify({ type: "error", detail: "Vote already cast" }));

    assert.equal(msg.kind, "error");
    assert.equal(msg.kind === "error" && msg.detail, "Vote already cast");
});

test("roundSocketUrl builds a ws URL from an http gateway base", () => {
    assert.equal(roundSocketUrl("http://localhost:8080", 42), "ws://localhost:8080/rounds/ws/42");
    assert.equal(roundSocketUrl("https://praim.example", 7), "wss://praim.example/rounds/ws/7");
});

test("each action sends exactly the message the RoomManager expects", () => {
    const sent: string[] = [];
    const client = new RoundClient({ send: (d: string) => sent.push(d) });

    client.join();
    client.ready();
    client.start();
    client.vote("re-star-borgo");
    client.chat("io voto re-star-borgo");

    assert.deepEqual(sent.map((s) => JSON.parse(s)), [
        { type: "join" },
        { type: "ready" },
        { type: "start" },
        { type: "vote", vocazione: "re-star-borgo" },
        { type: "chat", body: "io voto re-star-borgo" },
    ]);
});

test("an action clicked before the socket opens is buffered, then flushed on open", () => {
    const sent: string[] = [];
    // readyState 0 = CONNECTING: the user clicked before the handshake finished.
    const socket = { readyState: 0, send: (d: string) => sent.push(d) };
    const client = new RoundClient(socket);

    client.join();
    assert.deepEqual(sent, []); // nothing sent while still connecting

    socket.readyState = 1; // OPEN
    client.flush();
    assert.deepEqual(sent.map((s) => JSON.parse(s)), [{ type: "join" }]);
});
