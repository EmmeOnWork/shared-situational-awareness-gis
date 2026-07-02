"""The Vocazione→Competitor prefix map (strangler copy of the monolith's).

Pure lookup: a market Vocazione slug resolves to its FSQ category-label prefixes;
an empty or unknown slug resolves to ``[]`` — the signal the route reads as "no
market competitor" (civic archetypes).
"""

from src.routers.likert.vocazione_competitors import (
    VOCAZIONE_COMPETITORS,
    get_competitor_category_prefixes,
)


def test_market_vocazione_resolves_to_its_prefixes():
    prefixes = get_competitor_category_prefixes("dimora-del-benessere")

    assert prefixes
    assert prefixes == VOCAZIONE_COMPETITORS["dimora-del-benessere"]


def test_empty_slug_resolves_to_no_prefixes():
    assert get_competitor_category_prefixes("") == []


def test_unknown_slug_resolves_to_no_prefixes():
    assert get_competitor_category_prefixes("not-a-real-vocazione") == []
