# Building Characteristic Widget (PRAIM)

A standalone **write** Widget service that lets the responsible Workshop Master
attach a building's blueprint photos — and the building's reuse data — to a POI
clicked on the map. Unlike the demographic/pollution/weather Widgets it does not
just read: it stores binaries and performs authorized mutations. It shares the
Janus Supabase database (ADR-0001) and never edits the monolith.

## Language

### Building Characteristic domain

**Workshop**:
The unit of work around the reuse of a single confiscated/public **bene**: it
ties one **POI** to the material (Blueprints, Scheda) that describes how that
asset is being repurposed. Exactly one Workshop per bene/POI. Materialised as the
**registry table** of reuse-POIs (`building_workshop`, keyed by `poi_id`): the
canonical list of Bene the Selector reads — a Bene exists in it even when it has
no Scheda or Blueprints yet — and the future home of `master_user_id`.
_Avoid_: project, site (those are vaguer and overloaded)

**Workshop Master**:
The single user responsible for **one** Workshop. The intended-only actor allowed
to upload Blueprints / edit the Scheda, and only for **their own** POI — not
globally. Target authorization is two-level: a write **scope** (held via their
role) *and* ownership of *this* POI.
_Avoid_: admin (an admin is global; a Master is bound to one bene)

> **v1 scope (deferred roles):** authorization is **not** enforced yet. v1 keeps
> only baseline **authentication** — write routes require a valid JWT (any
> logged-in user), reusing the copied `get_current_user`; the bundle (`widget.js`)
> stays unguarded. No `building:write` scope, no per-POI ownership check, no DB
> role yet. The Master gate slots in later at a single seam (the route's
> dependency: add `require_scopes([...])` + ownership). Authentication is kept on
> writes precisely to avoid an open binary-upload endpoint.

**Bene**:
The real-world asset (a confiscated/public building) a Workshop is about. It is
a **special POI** — one *adibito al riuso*, the fulcrum of the dashboard — not an
ordinary map POI. A POI becomes a Bene by having a Workshop; only Bene POIs carry
a Scheda and Blueprints. Referenced through its **POI** by id; the service never
owns geometry. Identity source of truth = the POI (decision A): comune/coordinate
are shown from the POI, never re-stored; the Scheda owns only what the POI lacks
(denominazione edificio, estremi catastali) plus all reuse data (sections 2–6).

**Scheda** (Scheda di Individuazione Immobile):
The structured reuse data for one **Bene** — exactly one Scheda per Workshop/POI.
It is the standardised *Provincia di Avellino — "Scheda di Individuazione
Immobile"* form, not free prose: identification (comune, denominazione, indirizzo,
coordinate), tipologia/destinazione d'uso, titolo di proprietà/disponibilità,
stato d'uso e condizioni, vincoli, documentazione disponibile, and the comune's
technical referente. This is what the user first called "documento di riuso
caratteristico"; it is stored as **fields**, not an opaque PDF. It is created and
edited **through the widget's Load form**, alongside the Blueprint upload — *not*
only seeded externally (the Workshop *writes* the Scheda). Because it is 1:1 with
the Bene while Blueprints are N: the **first** Load creates it; **later** Loads
present it pre-filled and editable while only the new Blueprint differs. Its form fields are
**optional/non-blocking**: a Blueprint may be saved with the Scheda left empty.
Shown in the modal when any Blueprint is clicked; if absent, the modal says "non
disponibile".
_Avoid_: documento di riuso, scheda di riuso (use **Scheda**), PDF (it is data)

**Blueprint**:
One uploaded image of a black-and-white engineering drawing (planimetria)
attached to a Bene — the user's "foto di un blue-print". A Bene can have many
Blueprints, **one per Sezione** (floor or cross-section). The toggle list selects
which Sezione's Blueprint is shown. Stored as `bytea` in `public` (decision A),
served via `GET /characteristic/blueprints/{id}`.
_Avoid_: photo (too generic — these are technical plans), planimetria (acceptable
alias, but prefer Blueprint)

**Sezione** (floor or section):
The part of the building a Blueprint depicts — either a storey (*piano terra*,
*giardino*, *2° piano*) or a vertical cross-section (*sezione A-A*). The
discriminator that lets one Bene hold several Blueprints without collision: a
Blueprint is unique per `(Bene, Sezione)`. The toggle list is exactly the set of
Sezioni a Bene has.
_Avoid_: piano (too narrow — it excludes cross-sections)

### Inherited from the monolith

**POI** (Point of Interest):
The monolith's map entity (`id`, `source`, `source_id`, `name`, `geom`). A
clicked POI is the anchor everything in this Widget hangs off. This service
references a POI **by `id` only** and never reads its geometry.

**Widget** (write variant):
Unlike the read-only data-source Widget defined in the Demographic context, a
**write Widget** owns its own write/upload routes and does **not** speak the
read-only `DataResponse` contract. It still reuses the full-stack seam: a
self-contained custom element loaded via `{src, tag}`, JWT from the host, behind
the edge gateway, self-registered in the dashboard catalog.

**Active Workshop**:
The Bene/POI currently "under consideration" on the dashboard. Established by the
separate **Workshop Selector** widget and consumed by every **sensitive** widget.
This Widget is sensitive: it shows the Scheda + Blueprints of whatever POI is the
Active Workshop, and is empty/idle when none is selected. It depends only on the
contract (an Active Workshop `poiId`), never on the Selector's implementation.
_Avoid_: selected area (that is the coarser comune-level `area` filter, a
different, pre-existing channel)

**Sensitive widget**:
A widget that reacts to the **Active Workshop**. Transport (decided): a
browser-level event bus in the shared `window` — a `praim:workshop-selected`
CustomEvent plus a retained last value (e.g. `window.__praimActiveWorkshop`) read
at mount to survive late-join/HMR. No monolith edit, no host store. The Active
Workshop **survives a page reload**; persisting it (URL param recommended, so a
Bene's dashboard is shareable) is the Selector's responsibility — this Widget only
reads whatever retained value is present. Moving the GIS map is likewise the
Selector's/host's concern, out of this Widget's scope.

**Role / Scope**:
The monolith's auth model (`public.roles`, `public.scopes`, `public.role_scopes`;
JWT carries a `role` string and a space-separated `scope` claim). The Workshop
Master privilege is expressed as a write scope granted to a role, enforced here
with `require_scopes([...])` plus a per-POI ownership check.

## Flagged ambiguities

- **"Workshop master" vs "admin"** — resolved: a Master is scoped to a single
  bene/POI (ownership), not a global super-user. The DB role exists now; the
  per-POI ownership link is modelled now and assignment-at-registration comes
  later.
- **Two Scheda layouts** — five sample schede use the standardised *Provincia di
  Avellino* template; the older Cassano sheet (Consistenza, Estremi Catastali)
  has extra/renamed fields. Canonical schema = the standardised template; legacy
  fields map into it. (Open: exact final field list — see grilling.)
- **POI identity vs Scheda section 1** — resolved (decision A): the POI is the
  source of truth for geographic identity; the Scheda stores only what the POI
  lacks plus the reuse data.
- **Where Building data lives** — resolved: in this context's own `building_*`
  tables in `public` (workshop, scheda, blueprint). The monolith's `pois` table is
  referenced by `poi_id` only — **never written, no column added, no `metadata`
  reuse, no cross-domain FK** — because POIs are re-synced from external sources
  and the monolith owns them; piggybacking would be silently overwritten. Light
  list JSON (sezioni) is kept separate from the heavy `bytea`, served by id, so
  the UI loads a Blueprint only when its Sezione is shown.

## Anticipated direction (not built yet)

Roles/authorization arrive together with a richer access model: a **dashboard is
created by a Workshop Master or an admin**, who **invites** other users to
participate; invitees get access but with a **different role** (read/participate,
not write). This will likely refine **Workshop** into "a dashboard + its
participants around one Bene" and is where the **Workshop Master** ownership and
the `building:write` scope become real. Recorded so the v1 skeleton does not
foreclose it.
