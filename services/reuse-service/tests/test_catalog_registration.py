"""The catalog row's load-bearing shape — asserted in isolation (no DB).

``register_in_catalog`` runs only on real boot; what must stay stable is the
**row** it would write: the identity the dashboard renderer routes on and the
``{src, tag}`` that points the generic RemoteWidget seam at this service's bundle.
"""

from src.config.catalog_registration import _CATALOG_ROW, WIDGET_TYPE


def test_catalog_row_identity_is_reuse():
    assert WIDGET_TYPE == "reuse"
    assert _CATALOG_ROW["type"] == "reuse"


def test_catalog_row_points_remote_at_reuse_widget_bundle():
    """The renderer mounts a remote Widget from this fragment: the bundle URL the
    unguarded route serves, and the custom-element tag the element defines."""
    remote = _CATALOG_ROW["default_props"]["additionalConfig"]["remote"]

    assert remote == {"src": "/reuse/widget.js", "tag": "reuse-widget"}
