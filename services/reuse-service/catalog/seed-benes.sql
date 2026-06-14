-- v1 Bene seed — designate which POIs are Bene (reuse-POIs).
--
-- This is a **data step**, not service code. v1 seeds building_workshop directly
-- (PRD: "v1 may seed directly"); a polished admin curation UI is out of scope.
-- A Bene exists here even before it has a Scheda or Blueprints; the Selector's
-- GET /reuse/benes joins these poi_id values to public.pois for name + coords.
--
-- Replace the example ids below with the real POI ids of your reuse buildings.
-- Find them in the monolith's map data, e.g.:
--   SELECT id, name FROM public.pois WHERE name ILIKE '%caserma%';

INSERT INTO public.building_workshop (poi_id)
VALUES
    (101),   -- e.g. Ex Caserma
    (102)    -- e.g. Palazzo confiscato
ON CONFLICT (poi_id) DO NOTHING;
