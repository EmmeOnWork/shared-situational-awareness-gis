# The Round Manager runs its own WebSocket with a server-side room per Bene

Status: accepted

The Round Manager is the first Widget that needs **shared, mutable, realtime state
across many browsers**: the live "N/N hanno votato" tally, a round that closes for
everyone the instant the last vote lands, and an anonymous chat stream all
participants see live. We give the service **its own authenticated WebSocket with a
server-side room keyed per Bene (poi_id)**: a client subscribes to its current
Bene's room and receives pushes (vote registered → new tally, round opened/closed,
new chat message); round state lives in the service (DB + in-memory fan-out), not
in any client.

This deliberately **breaks the no-server-side-rooms rule the Realtime Notifier
holds** (ADR notification-service: the Notifier is fire-and-forget, broadcasts
globally, and filters by Scope client-side — "the moment it holds a room it has
become the Round Manager in disguise"). That rule keeps the *Notifier* generic; it
was never a system-wide ban. The Round Manager is the legitimate owner of round
domain state, so rooms belong here. The two transports stay orthogonal: the Round
Manager **produces** Notifications to the Notifier's publish ingress for the
toast/audio moments (round opened, round closed, consensus reached) **and**
separately serves its own WebSocket for round/chat state. The Notifier never carries
round state; the Round Manager's WebSocket never renders toasts.

## Considered options

- **Own WebSocket, per-Bene rooms (chosen).** The only honest way to get a live
  tally, simultaneous close, and a live chat. The service is already stateful and
  owns tables, so holding round state and rooms is consistent with its nature.
- **HTTP polling** (`GET /rounds/<bene>/state` + `/chat` every few seconds).
  Rejected: the tally and chat arrive in jerks and "closed for everyone at the same
  instant" becomes approximate; simpler but degrades the core realtime feel.
- **Reuse the Notifier's WebSocket.** Rejected: it would force domain rooms and
  round state into the Notifier, collapsing the load-bearing A/B split its context
  is built around. The Notifier stays a generic delivery surface.

## Consequences

- A second authenticated WebSocket convention behind the gateway (ADR-0002),
  distinct from the Notifier's. Both verify monolith JWTs (ADR-0001).
- Per-Bene rooms mean the server tracks connections by `poi_id`; reconnection must
  re-subscribe to the current Active Workshop's room.
- Round state must be durable (DB) *and* fanned out (in-memory), so a server restart
  mid-round must rehydrate the room from the DB.
