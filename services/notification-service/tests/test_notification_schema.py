"""The wire contract the Notifier understands — pydantic validation in isolation.

The Notifier is a dumb relay: it knows only `severity` + text and an optional
`scope`. It must never see a domain event type. These tests pin that contract:
what parses, what is rejected, and that `scope` is optional but well-formed when
present.
"""

import pytest
from pydantic import ValidationError

from src.notifier.notification import Notification


def test_valid_payload_parses():
    n = Notification(severity="info", title="Round aperto", body="Si vota")

    assert n.severity == "info"
    assert n.title == "Round aperto"
    assert n.body == "Si vota"
    assert n.scope is None


def test_unknown_severity_is_rejected():
    """`severity` is the only vocabulary the Notifier accepts; anything outside
    info/warning/success is rejected so a mis-classified producer event can never
    render."""
    with pytest.raises(ValidationError):
        Notification(severity="critical", title="x", body="y")


def test_scope_when_present_parses_axis_and_value():
    """An addressing hint against a selection-bus axis. Optional, but when given
    it carries both `axis` and `value` (the client matches its own selection
    against these — slice 5)."""
    n = Notification(
        severity="success",
        title="Consenso",
        body="Workshop concluso",
        scope={"axis": "workshop", "value": "42"},
    )

    assert n.scope.axis == "workshop"
    assert n.scope.value == "42"


def test_scope_missing_axis_or_value_is_rejected():
    """A half-specified scope cannot be matched, so it is rejected rather than
    silently treated as global."""
    with pytest.raises(ValidationError):
        Notification(
            severity="info", title="x", body="y", scope={"axis": "workshop"}
        )
