# geo-layers-service

External **data-source Widget** (strangler-fig, ADR-0001/0002): serves GeoJSON
map layers to the monolith's GIS map **without touching monolith code**. It sits
behind the edge gateway under `/geo-layers` (prefix already reserved in the
Caddyfile) and reads the shared local postgres.

It has **no UI bundle**: a map layer is added as *config data* on the JuMap widget
(`additionalConfig.layers`), not as a draggable widget — so there is no
`widget.js`, no custom element, and no catalog row.

## Layers

| route | layer | shape |
|---|---|---|
| `GET /geo-layers/fixed-under-1gb?region=CAMPANIA` | Rete fissa &lt; 1 Gb (under-served EGON civic addresses) | `{ "geojson": FeatureCollection<Point> }` |

Data routes are **auth-only** (any logged-in monolith user); the browser's JWT is
forwarded by the gateway. No extra scope to grant in the monolith.

## Map layer config (drop into the target map's `additionalConfig.layers`)

```json
{
  "name": "Rete fissa < 1 Gb",
  "useMarkers": true,
  "popupView": "table",
  "showProperties": { "comune": "Comune", "strada": "Via", "civico": "Civico" },
  "baseColor": { "color": "#6a1b9a", "fillColor": "#8e24aa", "fillOpacity": 0.7, "radius": 4 },
  "useGeoJSONFetchPath": "/geo-layers/fixed-under-1gb",
  "useGeoJSONFetchPathParams": { "region": "CAMPANIA" }
}
```

## Load the data (one-off; the schema comes up empty with the compose)

```sh
docker compose cp "data/Copertura_Digitale/Rete_Fissa_Sotto_1Gb/Allegato A_mapp707K.csv" \
    geo-layers-service:/tmp/civics.csv
docker compose cp services/geo-layers-service/db/load_civics.py \
    geo-layers-service:/tmp/load_civics.py
docker compose exec geo-layers-service python /tmp/load_civics.py /tmp/civics.csv --region CAMPANIA
```
