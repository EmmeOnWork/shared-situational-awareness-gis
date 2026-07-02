"""Catalog self-registration is best-effort: it never raises and is switchable.

The row's *shape* is what couples this Widget to the monolith's DB-driven "Add
widget" menu, so we pin it: a unique `type` plus the `remote` pointer the generic
RemoteWidget seam routes on. We do not touch a real database here.
"""

from unittest.mock import patch

from src.config import Settings, get_settings
from src.config.catalog_registration import _CATALOG_ROW, register_in_catalog


def test_catalog_row_carries_the_remote_pointer():
    """The catalog entry points the seam at this service's bundle + element."""
    assert _CATALOG_ROW["type"] == "likert"
    assert _CATALOG_ROW["category"] == "data"
    remote = _CATALOG_ROW["default_props"]["additionalConfig"]["remote"]
    assert remote == {"src": "/likert/widget.js", "tag": "likert-widget"}


def test_registration_skipped_when_disabled():
    """With the kill-switch off, registration is a no-op (no DB touched)."""
    get_settings.cache_clear()
    with patch(
        "src.config.catalog_registration.get_settings",
        return_value=Settings(register_in_catalog=False),
    ):
        assert register_in_catalog() is False
    get_settings.cache_clear()


def test_registration_is_best_effort_on_db_error():
    """A DB failure is swallowed (logged), never raised — the service stays up."""
    with patch(
        "src.config.catalog_registration.get_settings",
        return_value=Settings(
            register_in_catalog=True, database_url="postgresql+psycopg://x"
        ),
    ), patch(
        "src.config.catalog_registration.get_session_context",
        side_effect=RuntimeError("db down"),
    ):
        assert register_in_catalog() is False
