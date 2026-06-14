# characteristic-widget UI

The **frontend half** of the characteristic Widget: a single, framework-free
[custom element](https://developer.mozilla.org/en-US/docs/Web/API/Web_components)
`<characteristic-widget>`. The service serves the built bundle at
`/characteristic/widget.js`; the monolith's generic `RemoteWidget` seam loads it
and mounts the element. Nothing here depends on the monolith — the element runs in
any HTML page.

This is the walking skeleton (task 01): the element mounts in Shadow DOM and
renders a **neutral shell**, reading the host's `token` and `base`. Consuming the
Active Workshop, showing Blueprints/Scheda and the Load form arrive in later
slices.

## Host contract

| Attribute | Set by   | Meaning                                                     |
| --------- | -------- | ---------------------------------------------------------- |
| `token`   | the host | monolith-issued JWT; refreshed by the host on login/expiry |
| `base`    | the host | edge-gateway origin (`""` = same origin)                   |

The element calls only `/characteristic/*` on its own service, through the
gateway, with the host's JWT. See
`../../docs/architecture/widget-microservice-fullstack.md`.

## Build

```bash
npm install
npm run build      # → dist/characteristic-widget.js
```

`make ui` (from the service root) runs this and copies the bundle into
`src/static/` where FastAPI serves it. The production image builds it in a Node
stage (see the service `Dockerfile`); `dist/` is git-ignored.
