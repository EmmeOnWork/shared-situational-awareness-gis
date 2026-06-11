# Full-stack Widget microservices

## What it is

A **full-stack Widget** is a microservice that owns *both halves* of a dashboard
widget — its **data** (a FastAPI service) and its **UI** (a self-contained
[custom element](https://developer.mozilla.org/en-US/docs/Web/API/Web_components)).
The service serves its own UI bundle; the monolith only loads it. The result is a
widget you can drop into any host page, that survives the monolith — the
strangler-fig end state where the monolith is dormant and the Widgets remain.

This extends the [strangler-fig strategy](strangler-fig.md): that document
strangles the **backend** route by route; this one strangles the **frontend** the
same way, so a Widget no longer depends on the monolith's rendering code to draw
itself.

## When to read it

Before building a new Widget that needs its own UI (anything richer than reusing
an existing generic chart/table from a dashboard config), or when you need to
understand the one-time `remote` seam in the monolith and why it is the *only*
monolith edit the whole pattern ever needs.

## The core idea: one generic seam, then never the monolith again

The monolith's dashboard renderer used to be a closed `switch` over hard-coded
widget types (`JULineChart`, `PollutionChart`, …) with `default: "Unknown widget
type"` — no extension point. Adding a widget meant editing the monolith.

We added **one generic case**, `type: "remote"`, the frontend twin of the
[edge gateway](../adr/0002-edge-gateway-single-front-door.md)'s route table: a
dumb seam that, given `{ src, tag }`, loads a bundle and mounts a custom element.
It knows nothing about any specific widget. After this single, widget-agnostic
edit, **every** new full-stack Widget is added as *data* — a `{ src, tag }` entry
in a dashboard config — and the monolith's code is never touched again.

```mermaid
flowchart LR
    subgraph Monolith frontend (edited ONCE)
      WR[WidgetRenderer<br/>case 'remote'] --> RW[RemoteWidget<br/>generic loader]
    end
    subgraph demographic-service (owns both halves)
      JS[/demographics/widget.js<br/>custom element/]
      API[/demographics/* <br/>FastAPI + JWT/]
    end
    RW -- loads bundle --> JS
    JS -- fetch + Bearer JWT --> API
    RW -. passes token + base .-> JS
```

## The contract between host and Widget

The seam and the element meet at a tiny, fixed interface — the same shape for
every Widget:

| Direction | Carries | Detail |
| --------- | ------- | ------ |
| host → element, attribute `token` | the monolith-issued JWT | the host owns auth and refreshes this on login/expiry/logout; the element only consumes it |
| host → element, attribute `base` | the edge-gateway origin | `""` means same origin; the element calls only through the gateway |
| element → service | `Authorization: Bearer <token>` | the element calls **only its own** `/<prefix>/*` routes — never the monolith |

Two invariants make this safe and reusable:

- **The UI bundle is public; the data is not.** A browser `<script>` load carries
  no bearer token, so `GET /<prefix>/widget.js` is served **unguarded** while the
  data endpoints stay behind their scope. The *code* is public, the *data* is
  authorized at call time with the host's JWT.
- **One origin, always.** The bundle and its data both sit behind the gateway
  under the Widget's own prefix, so there is no second origin and no CORS — the
  same guarantee the strangler-fig backend already gives.

## How the demographic Widget realises it (the worked example)

| Piece | Where | What it does |
| ----- | ----- | ------------ |
| Custom element source | [`services/demographic-service/ui/src/demographic-widget.ts`](../../services/demographic-service/ui/src/demographic-widget.ts) | Framework-free `<demographic-widget>`: Shadow-DOM UI that reads `token`/`base`, fetches `/demographics/territories` + `/demographics/raw`, renders the profile. |
| UI build | [`services/demographic-service/ui/`](../../services/demographic-service/ui/) | esbuild → one minified IIFE bundle, no framework, no host coupling. |
| Bundle serving | [`services/demographic-service/src/app.py`](../../services/demographic-service/src/app.py) | `GET /demographics/widget.js` (app-level, **unguarded**) serves the built bundle. |
| Packaging | [`services/demographic-service/Dockerfile`](../../services/demographic-service/Dockerfile) | Node stage builds the bundle → Python stage serves API + bundle as one deployable. |
| Catalog registration | [`src/config/catalog_registration.py`](../../services/demographic-service/src/config/catalog_registration.py) + [`catalog/widget-type.sql`](../../services/demographic-service/catalog/widget-type.sql) | Inserts the Widget's row into the shared `widget_types` catalog so it appears in the "Add widget" menu — self-registering on boot, or via operator SQL. |
| Placement (config-as-code) | [`services/demographic-service/dashboard/widget.config.json`](../../services/demographic-service/dashboard/widget.config.json) | The exact widget entry the catalog produces — a ready-made drop-in for a dashboard's `widgets` array. The Widget owns *how it is shown*, versioned in its own repo. |
| Routing | [`edge-gateway/Caddyfile`](../../edge-gateway/Caddyfile) | `reverse_proxy /demographics*` already covers `widget.js` and the data routes — no new entry. |

## The dynamic "Add widget" menu (self-registration)

The dashboard's **"Add widget" menu is already dynamic**: it renders
`GET /dashboards/widget-types`, which is just
`SELECT … FROM dashboards_config.widget_types` — a table in the **shared
database** (ADR-0001). The monolith seeds that table on boot but its upsert
touches **only its own** seed rows (`ON CONFLICT (type) DO UPDATE` over a fixed
list), so a row owned by an external service **survives every monolith restart**.

That makes the catalog the registration seam: a Widget service appears in the menu
by inserting **one row** — pure data, no monolith code change. The row carries:

- a **unique `type`** (the catalog primary key; also the new widget's `type`), and
- `default_props.additionalConfig.remote = { src, tag }` — the pointer the generic
  seam routes on. The frontend's `makeWidget` copies `additionalConfig` into the
  freshly added widget, so the pointer flows from catalog → new widget → renderer
  with nothing widget-specific in between.

This is why the renderer routes by the **presence of `remote`**, not by a literal
`type === "remote"`: the catalog PK forces each Widget to have a distinct `type`,
yet all remote Widgets share the one generic `RemoteWidget`.

The demographic service registers itself two ways (pick one per environment):

| Mechanism | Where | When to use |
| --------- | ----- | ----------- |
| Self-registration on boot | [`src/config/catalog_registration.py`](../../services/demographic-service/src/config/catalog_registration.py) | Default. Best-effort upsert on startup; never fatal. Disable with `REGISTER_IN_CATALOG=false`. |
| Operator SQL | [`catalog/widget-type.sql`](../../services/demographic-service/catalog/widget-type.sql) | When the service's DB role may not write the monolith's `dashboards_config` schema. |

Self-registration is **best-effort**: if the catalog table is not there yet or the
role can't write it, the service logs and keeps serving data — registration is
never on the critical path.

## The one-time monolith change (what was edited, and why it is the last time)

Three small, **generic** changes — made once, for all Widgets:

1. [`WidgetRenderer.tsx`](../../monolith/frontend/src/app/dashboard/%5BdashboardMongoId%5D/WidgetRenderer.tsx)
   — before the type `switch`, routes any widget whose config carries
   `remote: { src, tag }` to `RemoteWidget`. It keys on the *presence* of the
   pointer, not on a widget name, so catalog-registered Widgets (each with a
   unique `type`) all share this one path.
2. [`RemoteWidget`](../../monolith/frontend/src/components/widgets/RemoteWidget/RemoteWidget.tsx)
   — new generic loader: loads a bundle once (deduped), mounts the custom
   element, feeds it the JWT (kept fresh via `subscribeToAuthChanges`) and the
   gateway origin.
3. [`EditableLayout/types.d.ts`](../../monolith/frontend/src/components/widgets/EditableLayout/types.d.ts)
   — added the generic optional `remote?: { src; tag }` field to `WidgetConfig`.

Why this is the *last* monolith edit: the per-widget surface is entirely in the
**config** (`src`, `tag`) and in the **service** (the element + its data). Nothing
in the three files above names a widget, so widget N reuses them unchanged. The
trap to avoid is a per-widget `case "demographic"` / `case "rounds"` — that would
send you back into the monolith every time. The seam stays generic precisely so
it never does.

## Adding a new full-stack Widget (the recipe)

Building on the strangler-fig backend recipe (claim a fresh prefix, share the DB,
verify the monolith JWT, speak `DataResponse`), the UI half adds:

1. **Build the element.** Under `services/<widget>/ui/`, define `<widget-name>` as
   a framework-free custom element. Read `token` and `base` attributes; call only
   your own `/<prefix>/*` routes with `Authorization: Bearer <token>`. Build to a
   single bundle (esbuild). Use Shadow DOM so your styles never leak into the host.
2. **Serve the bundle.** Add an **unguarded** `GET /<prefix>/widget.js` to the
   service that returns the built bundle. The gateway already routes `/<prefix>*`
   here, so no Caddyfile change.
3. **Package it.** A Node stage in the `Dockerfile` builds the bundle; the Python
   stage copies it next to the app. One deployable serves API + UI.
4. **Register it in the catalog (as data).** Insert one row into
   `dashboards_config.widget_types` with a unique `type` and
   `default_props.additionalConfig.remote = { src: "/<prefix>/widget.js", tag:
   "<widget-name>" }`. Do it by self-registration on boot (mirror
   `src/config/catalog_registration.py`) or an operator SQL seed (mirror
   `catalog/widget-type.sql`). The Widget then appears in the dynamic "Add widget"
   menu automatically.

Steps 1–4 touch **only** the new service and a shared-DB row. The monolith is not
edited.

## Invariants that must hold

- **The `remote` seam stays generic.** No widget-specific `case` in
  `WidgetRenderer`, no widget name in `RemoteWidget`. The day a widget name
  appears there, the pattern is broken.
- **`widget.js` is unguarded; data routes are guarded.** Never put the bundle
  behind the JWT (the `<script>` load can't send one); never drop the guard on the
  data routes.
- **The element talks only to its own service, through the gateway.** No absolute
  hosts, no calls to the monolith — same-origin, one JWT, no CORS.
- **Style isolation via Shadow DOM.** The Widget must not depend on, or pollute,
  the host's CSS — that is what keeps it droppable into any host.

## The trade-off, stated plainly

This pattern costs **one** generic monolith edit (the `remote` seam) and a small
per-Widget UI build. In return every Widget becomes a self-contained, independently
deployable unit that renders without the monolith. Compared to the config-only
approach (reusing the monolith's generic charts via a dashboard config), you give
up "zero monolith edits, ever" — paid once — and gain ownership of the *rendering*
itself, not just the composition. For a stack whose goal is Widgets that outlive
the monolith, that one-time cost is the correct price.

## Links out

- [The strangler-fig strategy](strangler-fig.md) — the backend half of the same move.
- [ADR-0001 — Shared database](../adr/0001-shared-database.md)
- [ADR-0002 — Edge gateway, single front door](../adr/0002-edge-gateway-single-front-door.md)
- [demographic-service](../../services/demographic-service/README.md) — the worked example.
