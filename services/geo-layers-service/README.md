# geo-layers-service

External **data-source Widget** (strangler-fig, ADR-0001/0002): serves GeoJSON
map layers to the monolith's GIS map **without touching monolith code**. It sits
behind the edge gateway under `/geo-layers` (prefix already reserved in the
Caddyfile) and reads the shared local postgres.

It has **no UI bundle**: a map layer is added as *config data* on the JuMap widget
(`additionalConfig.layers`), not as a draggable widget — so there is no
`widget.js`, no custom element, and no catalog row. The JuMap renderer already
draws polygons and colours them per feature (`colorCases`), so a new layer is just
a route here + a config entry on the target map.

## Structure — one folder per layer

```
src/
  app.py                 # mounts every layer router under /geo-layers (auth-only)
  core/                  # shared: db, security (JWT), settings, geojson helper
  layers/
    fixed_network/       # router.py + schema.sql + load.py
    frana/               # router.py + schema.sql   (data via ogr2ogr)
    idraulico/           # router.py + schema.sql   (data via ogr2ogr)
    sismico/             # router.py + schema.sql + load.py (comuni via ogr2ogr)
```

Each `layers/<name>/schema.sql` is applied (empty, idempotent) by the compose
`geo-layers-schema-init` one-shot on every bring-up; it loops over them, so adding
a layer is: drop a folder with a `schema.sql` + `router.py`, register the router
in `app.py`. The service never issues DDL (ADR-0001).

## Layers

| route | layer | shape | colour key |
|---|---|---|---|
| `GET /geo-layers/fixed-under-1gb?region_id=9` | Rete fissa &lt; 1 Gb (EGON civics) | `FeatureCollection<Point>` (markers) | — |
| `GET /geo-layers/frana?region_id=9` | Rischio frana (ISPRA PAI) | `FeatureCollection<MultiPolygon>` | `classe` (AA, P1..P4) |
| `GET /geo-layers/idraulico?region_id=9` | Rischio inondazione (ISPRA) | `FeatureCollection<MultiPolygon>` | `livello` (bassa/media/elevata) |
| `GET /geo-layers/sismico?region_id=9` | Rischio sismico (per comune) | `FeatureCollection<MultiPolygon>` | `zona` (1/2/3/3S/4) |

Every route is **scoped to one comune** via a required `region_id` (the clicked map
area), and clips/filters its features to that comune's boundary — the SAME comune
the monolith's POI/Confine layers follow, so a single map click drives all layers
and nothing loads the whole region up front. The configs opt in with
`reactToFilters.area` + a default `region_id` (see the templates below).

All data routes return `{ "geojson": <FeatureCollection> }` and are **auth-only**
(any logged-in monolith user); the browser's JWT is forwarded by the gateway. No
extra scope to grant in the monolith. The tables come up **empty** with the
compose schema-init — load each layer's data with the one-off steps below.

## Loading the data (one-off per database)

The risk datasets are national and large, so frana/idraulico are clipped to
Campania and reprojected to WGS84 (EPSG:4326) at load with `ogr2ogr` (GDAL). The
**route** then does the size reduction: it `ST_SimplifyPreserveTopology`s and
**dissolves to one MultiPolygon per class/level** (a few SVG paths instead of tens
of thousands) — so the heavy lifting is server-side, not in the load. Load from
the **original `.gdb` / `.shp`** (binary, read efficiently) — not the multi-GB
derived GeoJSONs, which GDAL loads whole into memory. The commands use a throwaway
GDAL container on the stack network (no image changes); run them from the repo
root with the stack up.

> Note: ogr2ogr's `-simplify` tolerance is in the **source** SRS units (metres
> here, not degrees), so it is omitted — the route simplifies in 4326 degrees
> instead. The frana `WHERE Shape_Area > 5000` just drops sub-0.5 ha noise.

- `janus-stack_janus-net` is `<compose-project>_janus-net` — check `docker network ls` if your project name differs.
- On Windows Git Bash, prefix with `MSYS_NO_PATHCONV=1` and use an absolute `-v` source (e.g. `-v "C:/.../data/Dati_Rischio:/data:ro"`) so the mount path isn't mangled.

### Rete fissa < 1 Gb (civics CSV → markers)

```sh
docker compose cp "data/Copertura_Digitale/Rete_Fissa_Sotto_1Gb/Allegato A_mapp707K.csv" \
    geo-layers-service:/tmp/civics.csv
docker compose exec geo-layers-service \
    python -m src.layers.fixed_network.load /tmp/civics.csv --region CAMPANIA
```

### Frana (`Frana.gdb`; reproject 32632→4326, clip + area-filter Campania)

`-spat` is the Campania bbox **in the source SRS** (EPSG:32632) — `-spat_srs` is
not allowed with `-sql`. Recompute it for another area with
`gdaltransform -s_srs EPSG:4326 -t_srs EPSG:32632`.

```sh
docker run --rm --network janus-stack_janus-net -v "$(pwd)/data/Dati_Rischio:/data:ro" \
  ghcr.io/osgeo/gdal:ubuntu-small-latest \
  ogr2ogr -f PostgreSQL "PG:host=ju-postgres user=janus password=CHANGE_ME dbname=janus" \
    /data/Frana/Frana.gdb \
    -sql "SELECT per_fr_ita FROM Mosaicatura_ISPRA_2024_aree_pericolosita_frana_PAI WHERE Shape_Area > 5000" \
    -nln frana_pericolosita -append -unsetFid -nlt PROMOTE_TO_MULTI \
    -t_srs EPSG:4326 -spat 883000 4415000 1091000 4629000
```

### Idraulico (`OLD/*.shp`; reproject 3035→4326, clip Campania)

One run per scenario shapefile; the `scenario` field tells the route the level.
`-spat` is the Campania bbox in the source SRS (EPSG:3035).

```sh
for shp in \
  HPH_Mosaicatura_ISPRA_2020_pericolosita_idraulica_elevata \
  MPH_Mosaicatura_ISPRA_2020_pericolosita_idraulica_media \
  LPH_Mosaicatura_ISPRA_2020_pericolosita_idraulica_bassa ; do
  docker run --rm --network janus-stack_janus-net -v "$(pwd)/data/Dati_Rischio:/data:ro" \
    ghcr.io/osgeo/gdal:ubuntu-small-latest \
    ogr2ogr -f PostgreSQL "PG:host=ju-postgres user=janus password=CHANGE_ME dbname=janus" \
      "/data/Idrogeologico/OLD/$shp.shp" \
      -sql "SELECT scenario FROM $shp" \
      -nln idraulico_pericolosita -append -unsetFid -nlt PROMOTE_TO_MULTI \
      -t_srs EPSG:4326 -spat 4622000 1863000 4829000 2075000
done
```

### Sismico (per-comune classification, coloured on the public.areas boundary)

The CSV has **no geometry**: the `/sismico` route draws the clicked comune's
boundary from `public.areas` (`area_type_id = 3`) and colours it by `ZONA_SISMICA`,
joined on the comune ISTAT code (`areas.metadata->>'ref:ISTAT'`). So only this CSV is
loaded — **no separate comuni-boundary import** — and the layer renders for exactly
the comuni `public.areas` has (the same ones POI/Confine cover).

```sh
docker compose cp data/Dati_Rischio/Sismico/classificazione_rischio_sismico_clean.csv \
    geo-layers-service:/tmp/sismico.csv
docker compose exec geo-layers-service \
    python -m src.layers.sismico.load /tmp/sismico.csv
```

> Reloading a layer: `TRUNCATE <table>;` first (the ogr2ogr step uses `-append`).
> frana/idraulico clip to one comune then simplify at `0.0003` (~33 m, near-lossless
> at that zoom); tune `ST_SimplifyPreserveTopology(…, 0.0003)` in the layer's
> `router.py` if needed (bigger = lighter/coarser).

## Map layer config (drop into the target map's `additionalConfig.layers`)

```json
{
  "name": "Rete fissa < 1 Gb",
  "useMarkers": true,
  "popupView": "table",
  "showProperties": { "comune": "Comune", "strada": "Via", "civico": "Civico" },
  "baseColor": { "color": "#6a1b9a", "fillColor": "#8e24aa", "fillOpacity": 0.7, "radius": 4 },
  "useGeoJSONFetchPath": "/geo-layers/fixed-under-1gb",
  "useGeoJSONFetchPathParams": { "region_id": "9" },
  "reactToFilters": { "area": true },
  "defaultVisible": false
}
```

```json
{
  "name": "Rischio frana",
  "useMarkers": false,
  "popupView": "table",
  "showProperties": { "classe": "Classe" },
  "baseColor": { "color": "#7f8c8d", "weight": 0.5, "fillOpacity": 0.55 },
  "colorCases": {
    "classe": {
      "AA": { "fillColor": "#fdd835", "color": "#f9a825", "weight": 0.5, "fillOpacity": 0.5 },
      "P1": { "fillColor": "#ffd54f", "color": "#fbc02d", "weight": 0.5, "fillOpacity": 0.55 },
      "P2": { "fillColor": "#ffb74d", "color": "#f57c00", "weight": 0.5, "fillOpacity": 0.6 },
      "P3": { "fillColor": "#ff8a65", "color": "#e64a19", "weight": 0.5, "fillOpacity": 0.65 },
      "P4": { "fillColor": "#e53935", "color": "#b71c1c", "weight": 0.5, "fillOpacity": 0.7 }
    }
  },
  "useGeoJSONFetchPath": "/geo-layers/frana",
  "useGeoJSONFetchPathParams": { "region_id": "9" },
  "reactToFilters": { "area": true },
  "defaultVisible": false
}
```

```json
{
  "name": "Rischio inondazione",
  "useMarkers": false,
  "popupView": "table",
  "showProperties": { "livello": "Livello" },
  "baseColor": { "color": "#1565c0", "weight": 0.3, "fillOpacity": 0.4 },
  "colorCases": {
    "livello": {
      "bassa": { "fillColor": "#90caf9", "color": "#1976d2", "weight": 0.3, "fillOpacity": 0.4 },
      "media": { "fillColor": "#42a5f5", "color": "#1565c0", "weight": 0.3, "fillOpacity": 0.5 },
      "elevata": { "fillColor": "#1565c0", "color": "#0d47a1", "weight": 0.3, "fillOpacity": 0.6 }
    }
  },
  "useGeoJSONFetchPath": "/geo-layers/idraulico",
  "useGeoJSONFetchPathParams": { "region_id": "9" },
  "reactToFilters": { "area": true },
  "defaultVisible": false
}
```

```json
{
  "name": "Rischio sismico",
  "useMarkers": false,
  "popupView": "table",
  "showProperties": { "comune": "Comune", "zona": "Zona sismica" },
  "baseColor": { "color": "#555555", "weight": 0.5, "fillOpacity": 0.55 },
  "colorCases": {
    "zona": {
      "1": { "fillColor": "#d32f2f", "color": "#b71c1c", "weight": 0.5, "fillOpacity": 0.6 },
      "2": { "fillColor": "#f57c00", "color": "#e65100", "weight": 0.5, "fillOpacity": 0.6 },
      "3S": { "fillColor": "#fbc02d", "color": "#f9a825", "weight": 0.5, "fillOpacity": 0.55 },
      "3": { "fillColor": "#fdd835", "color": "#fbc02d", "weight": 0.5, "fillOpacity": 0.55 },
      "4": { "fillColor": "#388e3c", "color": "#1b5e20", "weight": 0.5, "fillOpacity": 0.5 }
    }
  },
  "useGeoJSONFetchPath": "/geo-layers/sismico",
  "useGeoJSONFetchPathParams": { "region_id": "9" },
  "reactToFilters": { "area": true },
  "defaultVisible": false
}
```
