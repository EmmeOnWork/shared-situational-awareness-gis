"""Unit tests for the pure territory-list builder (rows -> list[Territory]).

No TestClient, no DB — assembly must be testable in isolation, mirroring the
build_demographic_response unit tests.
"""

from src.routers.demographics.demographics_router import build_territory_list


def test_build_territory_list_maps_rows_to_name_level():
    rows = [
        {"territory_name": "Avellino", "level": "province"},
        {"territory_name": "Italia", "level": "national"},
    ]

    result = build_territory_list(rows)

    assert [t.model_dump() for t in result] == [
        {"name": "Avellino", "level": "province"},
        {"name": "Italia", "level": "national"},
    ]
