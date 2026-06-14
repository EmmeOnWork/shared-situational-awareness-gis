"""Unit tests for the pure Bene-list builder (rows -> list[Bene]).

No TestClient, no DB — assembly must be testable in isolation, mirroring the
demographic service's build_territory_list unit test.
"""

from src.routers.benes.benes_router import build_bene_list


def test_build_bene_list_maps_rows_to_poi_id_name_coords():
    rows = [
        {"poi_id": 101, "name": "Ex Caserma", "lat": 40.9151, "lng": 15.4344},
        {"poi_id": 102, "name": "Palazzo Confiscato", "lat": 41.0073, "lng": 15.5021},
    ]

    result = build_bene_list(rows)

    assert [b.model_dump() for b in result] == [
        {"poiId": 101, "name": "Ex Caserma", "lat": 40.9151, "lng": 15.4344},
        {"poiId": 102, "name": "Palazzo Confiscato", "lat": 41.0073, "lng": 15.5021},
    ]


def test_build_bene_list_omits_bene_with_unresolved_poi():
    """A Bene whose POI row is missing comes back from the LEFT JOIN with null
    name/coords. It is **omitted**: a nameless, un-pannable entry is noise in the
    toggle-list and could not publish a valid Active Workshop."""
    rows = [
        {"poi_id": 101, "name": "Ex Caserma", "lat": 40.9151, "lng": 15.4344},
        {"poi_id": 999, "name": None, "lat": None, "lng": None},  # POI row missing
    ]

    result = build_bene_list(rows)

    assert [b.model_dump() for b in result] == [
        {"poiId": 101, "name": "Ex Caserma", "lat": 40.9151, "lng": 15.4344},
    ]
