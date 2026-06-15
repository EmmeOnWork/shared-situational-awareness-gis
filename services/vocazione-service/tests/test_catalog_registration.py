"""The catalog row's load-bearing shape — asserted in isolation (no DB).

``register_in_catalog`` runs only on real boot; what must stay stable is the
**row** it would write: the identity the dashboard renderer routes on and the
``{src, tag}`` that points the generic RemoteWidget seam at this service's bundle.
"""

from src.config.catalog_registration import _CATALOG_ROW, _UPSERT, WIDGET_TYPE


def test_catalog_row_identity_is_vocazione():
    assert WIDGET_TYPE == "vocazione"
    assert _CATALOG_ROW["type"] == "vocazione"


def test_catalog_row_is_a_data_widget():
    """The siblings have no `filter` category, so the Selector ships as `data`."""
    assert _CATALOG_ROW["category"] == "data"


def test_catalog_row_points_remote_at_vocazione_widget_bundle():
    """The renderer mounts a remote Widget from this fragment: the bundle URL the
    unguarded route serves, and the custom-element tag the element defines."""
    remote = _CATALOG_ROW["default_props"]["additionalConfig"]["remote"]

    assert remote == {"src": "/vocazione/widget.js", "tag": "vocazione-widget"}


def test_upsert_is_idempotent():
    """Boot self-registration must be repeatable: re-running it refreshes the
    code-owned default_props in place rather than erroring on the existing row."""
    sql = str(_UPSERT)

    assert "ON CONFLICT (type) DO UPDATE" in sql
