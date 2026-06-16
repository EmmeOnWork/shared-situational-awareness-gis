# Realtime Notifier Widget (PRAIM)

A standalone, **stateless / ephemeral** realtime Widget service (prefix `/notifications`,
anticipated by the strangler-fig doc). Its only job is to hold an authenticated
WebSocket connection and **render self-describing notifications** — a top-right toast
plus an audio alert — pushed from the server. Unlike every other Widget it is **not a
grid card**: it mounts as a **chromeless, page-global overlay** (ADR-0006), invisible
until a toast arrives. It is a *delivery surface*, not a domain:
it never stores anything, never knows what a "round" is, and owns no tables. The
**round logic that produces these notifications lives in a separate, future widget**
(see **Round Manager**, out of current scope).

## Language

### Notification domain

**Notification**:
A single transient alert delivered over the WebSocket and rendered as a top-right
**toast** + an **audio alert**. It is **self-describing**: it carries presentation-level
fields (a `severity` such as `info | success | warning` that maps to a sound + colour,
plus `title`/`body` text) and *optionally* a **scope**. It carries **no domain event
type** — the Notifier never sees `round_closed`; it sees a `severity` and some text.
Fire-and-forget: never stored, never replayed on reconnect.
_Avoid_: message, event (those imply the domain semantics that live in the producer),
push (be specific).

**Realtime Notifier**:
The widget itself (service `notification-service`). Owns three things: the
authenticated WS connection, the toast overlay, the audio playback. Plus a server-side
**publish ingress** (`POST /notifications/publish`) that fans a Notification out to all
connected clients. The caller is **the system, automatically** — an automated
server-side producer (the future Round Manager's backend), never an end user clicking a
button, and never the Notifier watching a domain table itself. Authorisation on the
ingress (who may call it) is a separate, deferred decision. Stores nothing.
_Avoid_: notification widget (use Notifier), message bus (too vague — it renders, it
doesn't just relay).

**Severity**:
The presentation category a Notification carries (`info | success | warning`). The
Notifier maps it to a sound + colour. This is the **only** vocabulary the Notifier
understands; the *producer* classifies its domain event into a severity. Keeps the
Notifier generic.
_Avoid_: type, level, kind (when you mean the domain event — that is the producer's).

**Scope** (optional):
An optional addressing hint on a Notification, expressed against the **selection bus**
axes (e.g. `{ axis: "workshop", value: <beneId> }`). A client renders a scoped
Notification only if its own current selection on that axis matches; an unscoped
Notification is global. The server still broadcasts to everyone — the scope is a
*client-side filter*, reusing ADR-0003/0005 rather than server-side rooms.
_Avoid_: room, channel, topic (those imply server-side routing we deliberately avoid).

### Inherited / referenced

**Round** *(belongs to the future Round Manager, not here)*:
A decisional voting cycle within a workshop over a **Bene**. Has named lifecycle moments
— **round opened**, **round closed** (everyone has voted), **consensus reached**
(everyone agrees → workshop done, move to the next reuse). These are the *producer's*
domain events; the Notifier only ever receives them already classified into a
**Severity** + text. **Round state/history is per-Bene and persistent** (e.g. "stopped
at round 9", "3 rounds last week") — that is the Round Manager's stored data, **never**
the Notifier's.

**Active Workshop**:
The single page-global selection of which **Bene** is under consideration (ADR-0003),
published by the Workshop Selector (reuse-service) on the selection bus. The Notifier
references it only as the value a scoped Notification's `workshop` axis is matched
against; it does not publish or own it.

**Bene**:
The confiscated/public building (a special POI) a round is about, owned by the Building
Characteristic context. Named here only as the value carried in a Notification's
**Scope**.

## Flagged ambiguities

- **Notifier (A) vs Round Manager (B) — the load-bearing split.** A is a generic,
  stateless *delivery surface* (WS + toast + audio) that understands only **Severity**
  and **Scope**. B (future, out of scope) owns the **Round** domain: the lifecycle, the
  per-Bene state/history, the decision of *when* an event fires and *which* severity it
  maps to. A is built first and is then immediately ready to render whatever B produces.
  The split holds **only if A never branches on a domain event type** — the moment the
  Notifier contains `if (type === "round_closed")`, it has become B in disguise.
- **"message"/"event" are overloaded.** Over the wire it is a **Notification** (carries
  severity + text, not domain meaning). The *domain* `round_opened`/`round_closed`/
  `consensus_reached` are **B's events**, which never reach the Notifier as such.
- **Delivery scope is a client filter, not a server room.** There are no server-side
  rooms/topics; the server broadcasts globally and clients suppress Notifications whose
  **Scope** does not match their current selection (the receiver's **Active Workshop**).

## Example dialogue

> **Dev:** Everyone voted, the round closes. What does the Notifier do?
> **Domain:** Nothing on its own — it doesn't know a round exists. The **Round Manager**
> decides "round closed → severity `success`, title 'Round chiuso'", POSTs that to the
> Notifier's publish ingress, and the Notifier fans it out: toast + sound for everyone
> connected.
> **Dev:** So the Notifier knows we were on round 9?
> **Domain:** Never. Round counting and history are the Round Manager's stored,
> per-Bene state. The Notifier is fire-and-forget; reconnect and you've missed nothing
> because there was nothing to remember.
> **Dev:** Two users have different Benes selected. Who hears the sound?
> **Domain:** If the Notification carries a `scope` of `{axis: "workshop", value: X}`,
> only the user whose Active Workshop is X renders it; the other suppresses it. Same
> selection bus the characteristic widget already reacts to — no server-side rooms.
