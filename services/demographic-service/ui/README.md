# demographic-widget UI

The **frontend half** of the demographic Widget: a single, framework-free
[custom element](https://developer.mozilla.org/en-US/docs/Web/API/Web_components)
`<demographic-widget>`. The service serves the built bundle at
`/demographics/widget.js`; the monolith's generic `RemoteWidget` seam loads it and
mounts the element. Nothing here depends on the monolith — the element runs in any
HTML page.

## Host contract

| Attribute | Set by   | Meaning                                                   |
| --------- | -------- | -------------------------------------------------------- |
| `token`   | the host | monolith-issued JWT; refreshed by the host on login/expiry |
| `base`    | the host | edge-gateway origin (`""` = same origin)                 |

The element calls only `/demographics/*` on its own service, through the gateway,
with the host's JWT. See `../../docs/architecture/widget-microservice-fullstack.md`.

## Build

```bash
npm install
npm run build      # → dist/demographic-widget.js
```

`make ui` (from the service root) runs this and copies the bundle into
`src/static/` where FastAPI serves it. The production image builds it in a Node
stage (see the service `Dockerfile`); `dist/` is git-ignored.
