# Round Manager Widget (PRAIM)

The widget anticipated (and deferred) by the Realtime Notifier and the context map
as **Round Manager**. Unlike every prior Widget — which is either *stores-nothing*
or *single-client read/write* — this one is **stateful, multi-user and realtime-
shared**: it runs a structured, iterative group **consensus process** over the
current **Bene**, persists each **Round**'s outcome and timings, and is the
server-side **producer** that POSTs Notifications to the Realtime Notifier. Behind
the edge gateway under the `/rounds` prefix (the prefix ADR-0002 already reserved).

## Language

### Round domain

**Round**:
One decisional voting cycle over the current **Bene**: every participant casts a
single **Vote**, the round **closes** once all have voted, a **Consensus** value is
computed, and (if not yet total) a **new Round** begins after deliberation. Has the
lifecycle moments the Notifier context named — **round opened**, **round closed**
(everyone voted), **consensus reached** (Consensus = 100%). Round state and history
are **per-Bene and persistent**. The **roster (denominator "N") is frozen for the
duration of a Round** and can change only *between* Rounds (via the phase-3 "pronti
a ricominciare" ready-signal); a user who joins mid-Round enters the *next* Round,
never the current one — so "N/N hanno votato" is a deterministic close and each
Round's N and timings are stable for analysis. **Every Round opens through the same
ready-gate** — between Rounds it is the phase-3 "inizia nuovo round" readiness;
**Round 1 opens through a phase-0 lobby** (participants join — bringing the Role
their account carries — and the ready ones start it), so there is no special case
for the first Round.
Rounds **repeat without an upper bound** until Consensus = 100%.
_Avoid_: vote (a Round contains many), session, poll.

**Vote**:
A single participant's chosen **Vocazione** for the current **Bene** in the current
**Round** — picked from the *same 16-archetype catalog* the Vocazione Selector owns,
but a **distinct selection**: a *ballot*, not a filter lens. It is **not** published
on the selection bus and is **not** the Active Vocazione. A Vote is **final on
confirmation** (the confirm modal is the point of no return): it cannot be changed
within the Round — the dropdown disappears once cast — so "X rimasti" only ever
counts down. Changing one's mind happens in the *next* Round, after deliberating in
the **Chat**.
_Avoid_: choice (too vague), selection (collides with the selection bus), Active
Vocazione (that is the personal filter, a different axis entirely).

**Consensus**:
A **nominal, exact-match** measure of agreement among participants on their
**Votes**, in [0,1]: two participants agree only if they chose the *same*
Vocazione (no partial credit for "similar" archetypes — the 16 are a nominal
catalog with no defined distance, which rules out ordinal measures like
Tastle–Wierman). Defined as **one minus normalized Shannon entropy** of the vote
distribution: `C = 1 − H / ln k`, `H = −Σ pᵢ ln pᵢ`. It is 0 at maximal dispersion
and **1 iff unanimity** — so "Consensus = 100%" is exactly "everyone voted the same
Vocazione," the stop condition. Computed at **two levels**: per **Role** (the
radar's branch intensity — intra-role cohesion) and pooled over **all** participants
("consenso totale"). The design preconditions a distributional measure needs — fixed
support (closed 16-catalog), independent observations (one secret, final Vote each),
fixed N (frozen roster) — are already guaranteed by the rest of this context.
_Avoid_: agreement (reserve for the colloquial sense), score.

**Winning category**:
The single **Vocazione** everyone converged on when overall **Consensus** reaches
100%. It ends the process. It is persisted **internally** in the Round Manager's
Round history (with the number of Rounds and timings) and shown in the phase-4
recap, but is **not** written as a cross-context Bene → Vocazione link (ADR-0003):
the deferred map-layer link stays deferred until a real consumer exists.
_Avoid_: winner, choice, result (be specific).

**Participant**:
A user taking part in a Bene's consensus process. The roster is **self-forming**:
there is **no per-Bene access list** in the system (access is scope-granular —
`reuse:read` exposes *every* Bene), so a user becomes a Participant by **joining**
this Bene's round, not by being on a pre-authorized list. Identified by the JWT
`sub` (user_id); the Round Manager **owns** the participants table (a row per
user×Bene), since no existing table models Bene membership.
_Avoid_: member (no membership list exists), user (reserve for the monolith's
account), voter (a Participant who hasn't voted yet is still a Participant).

**Role** (stakeholder taxonomy):
The participatory-workshop stakeholder category a Participant holds — **tecnico,
istituzionale, economico** (a closed catalog of three the Round Manager mirrors). It
is the **radar's branches** and the grouping for *intra-role* Consensus. It is **not**
the monolith's JWT `role` (an auth role), but it **is** a property of the user account:
**chosen once at registration** in the monolith, persisted on `public.users`, and
carried on the JWT as the **`stakeholder_role` claim**. The Round Manager reads it off
the **verified handshake** and seeds it on `join` — there is **no in-lobby Role
declaration** (a legacy token minted before the claim existed is rejected at join, so
the user re-logs in to refresh it). _Avoid_: role unqualified (collides with the JWT
auth `role` — always say *stakeholder role* when ambiguous), category (that is the
Vocazione/winner).

**Chat**:
A **per-Bene, continuous** anonymous message stream that spans *all* the Bene's
Rounds (the deliberation log that lets participants change their mind between
Rounds). **Write access unlocks only after the participant has cast their Vote in
the current Round** — this preserves the **independence of Votes** that the
Consensus measure assumes (you cannot read others' arguments before voting). It
stays **read-only in the recap** (phase 3). Anonymity is **total**: no author is
ever shown (level (a)); the server retains the author's user_id internally for
abuse control only, never exposes it, and the analyzable record carries timestamp +
Round number but no identity. Persisted (part of the process under study).
_Avoid_: comments, thread (it is one continuous stream per Bene), room (the realtime
room is the transport, the Chat is the content).

### Inherited / referenced

**Notification** *(produced, owned by the Realtime Notifier context)*:
The Round Manager **backend is the producer** that POSTs to the Notifier's publish
ingress for the **shared lifecycle moments only** — **round closed** (`info`), **new
round opened** (`info`), **consensus reached** (`success`) — each carrying the Bene's
**Scope** (`{axis:"workshop", value: beneId}`) so only participants whose Active
Workshop is that Bene see the toast/hear the sound. A **Vote carries no
Notification**: confirming a Vote is purely **local widget feedback** (the modal →
"HAI VOTATO" transition), because the Notifier broadcasts globally and cannot target
the single voter, and a per-Vote sound would be noise.

**Vocazione**:
One of the 16 fixed reuse archetypes owned by the **Vocazione Selector** context.
Here it is the *set of options a Vote chooses among* and, at total Consensus, the
**winning category** decided for the Bene. NB the Vocazione context records **no
stored building→Vocazione link** as deliberate; a Round reaching consensus is the
first thing that would *produce* such a (Bene → Vocazione) decision.

**Bene**:
The confiscated/public building (a special POI) a Round is about, owned by the
Building Characteristic context. The current Bene is the **Active Workshop**.

**Active Workshop**:
The page-global selection of which **Bene** is under consideration (ADR-0003/0005),
published by the Workshop Selector. The Round Manager is a **sensitive widget**: it
**consumes** the Active Workshop (never publishes it) and shows the Round of *that*
Bene — every per-Bene thing (WebSocket room, roster, Chat, Round history) keys off
it. **No Active Workshop ⇒ empty state** ("seleziona un Bene"): no Bene, no room, no
Round. Switching the Active Workshop re-subscribes the widget to the other Bene's
room and shows that Bene's Round (possibly a different phase); a Vote already cast on
the first Bene stays valid (Votes are per-Bene).

## Flagged ambiguities

- **Vote vs Active Vocazione — same catalog, different axis.** Both pick from the 16
  Vocazioni. The **Active Vocazione** (vocazione-service) is a page-global *filter
  lens* published on the selection bus. A **Vote** is a private *ballot* inside a
  Round, never on the bus. Same options, opposite meaning.
- **A Round closes only on full presence-unanimity — no escape hatch (deliberate,
  provisional).** "N/N hanno votato" is the *only* way a Round closes: a single
  frozen-roster participant who never votes blocks that Bene's process indefinitely.
  This risk is accepted **for now**; a timeout, a facilitator force-close, or a
  quorum (< 100% presence) are explicitly deferred to a future refactor. Reversible
  and additive, so not recorded as an ADR.
