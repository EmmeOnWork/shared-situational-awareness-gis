"""The catalog row's load-bearing shape — asserted in isolation (no DB).

``register_in_catalog`` runs only on real boot; what must stay stable is the
**row** it would write: the identity the dashboard renderer routes on, the
``placement: "overlay"`` flag that sends this bundle to the page-global overlay
seam (ADR-0006) rather than a grid card, and the ``{src, tag}`` that points the
generic remote seam at this service's bundle.
"""

from src.config.catalog_registration import _CATALOG_ROW, _UPSERT, WIDGET_TYPE


def test_catalog_row_identity_is_notifications():
    assert WIDGET_TYPE == "notifications"
    assert _CATALOG_ROW["type"] == "notifications"


def test_catalog_row_is_flagged_overlay_placement():
    """The Notifier is NOT a grid card: the declarative `placement: "overlay"`
    flag in default_props is what the monolith's <RemoteOverlay> seam queries to
    mount this bundle page-global and chromeless (ADR-0006)."""
    assert _CATALOG_ROW["default_props"]["placement"] == "overlay"


def test_catalog_row_points_remote_at_notification_overlay_bundle():
    """The overlay seam mounts a remote element from this fragment: the bundle
    URL the unguarded route serves, and the custom-element tag the element
    defines."""
    remote = _CATALOG_ROW["default_props"]["additionalConfig"]["remote"]

    assert remote == {"src": "/notifications/widget.js", "tag": "notification-overlay"}


def test_upsert_is_idempotent():
    """Boot self-registration must be repeatable: re-running it refreshes the
    code-owned default_props in place rather than erroring on the existing row."""
    sql = str(_UPSERT)

    assert "ON CONFLICT (type) DO UPDATE" in sql
