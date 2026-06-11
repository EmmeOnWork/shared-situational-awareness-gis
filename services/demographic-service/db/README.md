# Demographic data table — schema vs. data

The demographic widget reads `public.demographic`. We split that table into two
deliberately separate concerns:

- **Schema (automatic, via compose).** `demographic-schema.sql` creates the empty
  table. The root `docker-compose.yml` runs it on every bring-up through the
  one-shot `demographic-schema-init` service (idempotent — `CREATE TABLE IF NOT
  EXISTS`). The service itself never issues DDL: it stays a pure reader
  (ADR-0001), so the schema comes up with the infrastructure, not the app.

- **Data (manual, one-off).** Rows are **not** loaded by compose. Load them once
  per database from the source CSV:

  ```bash
  # from the repo root, with the stack up
  docker compose exec -T ju-postgres \
    psql -U janus -d janus -v ON_ERROR_STOP=1 \
    -c "\copy public.demographic FROM STDIN WITH (FORMAT csv, HEADER true)" \
    < data/demographic.csv
  ```

  The CSV column order matches the table, so a plain `\copy ... CSV HEADER`
  loads it as-is. Re-running replaces nothing; to reload, `TRUNCATE
  public.demographic;` first (or use `INSERT ... ON CONFLICT` if you script it).

## Province boundaries (manual, one-off) — for map-click resolution

`/demographics/at-point` resolves a map click (a lat/lng) to the province that
contains it, so the widget can react to the dashboard's area filter even though
the click lands on a *comune* the demographic data does not carry. That needs one
polygon per province in `public.demographic_boundary` (created empty by
`demographic-schema.sql`, same schema-vs-data split as above).

Load them once per database from an ISTAT province boundary GeoJSON
(EPSG:4326, e.g. the "Confini delle unità amministrative — Province/UTS" export):

```bash
# from the repo root, with the stack up
docker compose cp services/demographic-service/db/load_boundaries.py \
    demographic-service:/tmp/load_boundaries.py
docker compose cp provinces.geojson demographic-service:/tmp/provinces.geojson
docker compose exec demographic-service \
    python /tmp/load_boundaries.py /tmp/provinces.geojson --name-field DEN_UTS
```

`load_boundaries.py` reconciles each polygon's name to the exact
`territory_name` already in `public.demographic` (it FK-references it), applying a
small `OVERRIDES` map for ISTAT spellings that differ (e.g. `Bolzano/Bozen` →
`Bolzano-Bozen`). Any polygon it can't match is printed at the end — add it to
`OVERRIDES` and re-run (the load is idempotent: it upserts by `territory_name`).
Until this runs, `/demographics/at-point` answers `503` ("boundaries not loaded")
and the widget falls back to its manual dropdown.

## Why this split

The table is created reproducibly by infrastructure, while the data — a static
ISTAT snapshot — is loaded explicitly. This keeps the service non-atomic on
purpose: it does not seed or own its datastore at runtime, matching the shared-DB
decision (ADR-0001) where the operator controls what lands in the shared
database.

## Schema shape

A wide row per Territory, name-keyed, no geometry, no time series — unlike
pollution (which is normalised because it carries geometry + a time series).
`territory_name` is unique across all four scales (province / region /
macro_area / national), so it is the primary key the router looks up by.
