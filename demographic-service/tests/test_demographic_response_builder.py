"""Unit tests for the pure response builder (row -> DataResponse).

No TestClient, no DB — assembly must be testable in isolation.
"""

from src.routers.demographics.demographics_router import build_demographic_response


def _row(**overrides):
    row = {
        "territory_name": "Milano",
        "territory_name_istat": "Milano",
        "level": "province",
        "pop_total": 3214.0,
        "pop_italian": 2789.0,
        "pop_foreign": 425.0,
        "age_share_0_14": 12.6,
        "age_share_15_64": 63.9,
        "age_share_65_plus": 23.5,
        "mig_rate_internal": -1.2,
        "mig_rate_foreign": 7.8,
        "mig_rate_total": 6.6,
    }
    row.update(overrides)
    return row


def test_label_is_the_territory_name():
    resp = build_demographic_response(_row(territory_name="Avellino"))

    assert resp.label == "Avellino"


def test_data_carries_all_nine_indicators():
    resp = build_demographic_response(_row())

    assert resp.data == {
        "pop_total": 3214.0,
        "pop_italian": 2789.0,
        "pop_foreign": 425.0,
        "age_share_0_14": 12.6,
        "age_share_15_64": 63.9,
        "age_share_65_plus": 23.5,
        "mig_rate_internal": -1.2,
        "mig_rate_foreign": 7.8,
        "mig_rate_total": 6.6,
    }


def test_datetimes_are_null_demographics_are_not_a_time_series():
    resp = build_demographic_response(_row())

    assert resp.from_datetime is None
    assert resp.to_datetime is None


def test_metadata_echoes_the_territory_and_level_actually_answered():
    """The echoed Territory + level is load-bearing: it lets the Selection layer
    honestly label a province-level value when the user clicked something finer
    (e.g. comune Monteverde resolved to province Avellino)."""
    resp = build_demographic_response(
        _row(territory_name="Avellino", level="province")
    )

    assert resp.metadata["territory_name"] == "Avellino"
    assert resp.metadata["level"] == "province"


def test_metadata_carries_reading_context_so_numbers_are_read_correctly():
    """Population is in thousands as of ISTAT Table 1's reference date; the
    migration rates are for ISTAT Table 4's reference year."""
    resp = build_demographic_response(_row())

    assert resp.metadata["population_unit"] == "thousands"
    assert resp.metadata["population_reference_date"] == "2026-01-01"
    assert resp.metadata["rates_reference_year"] == 2025


def test_metadata_quality_flags_label_each_indicator_S_estimated_or_P_provisional():
    """The (S) estimated / (P) provisional flags are column-uniform (per ISTAT
    header), so the caller can label any value truthfully. Totale population and
    every migration rate are provisional (P); Italian/foreign population and the
    age shares are estimated (S)."""
    resp = build_demographic_response(_row())

    assert resp.metadata["quality_flags"] == {
        "pop_total": "P",
        "pop_italian": "S",
        "pop_foreign": "S",
        "age_share_0_14": "S",
        "age_share_15_64": "S",
        "age_share_65_plus": "S",
        "mig_rate_internal": "P",
        "mig_rate_foreign": "P",
        "mig_rate_total": "P",
    }
