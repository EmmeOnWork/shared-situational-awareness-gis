import pytest
from pydantic import ValidationError

from src.models.workshop import Scheda


@pytest.mark.parametrize(
    "field,good,bad",
    [
        ("stato_uso", "dismesso", "abbandonato"),
        ("condizioni", "buone", "ottime"),
    ],
)
def test_single_value_enum_fields_reject_unknown_accept_allowed(field, good, bad):
    """The strict single-valued enum-like fields accept a value from their allowed
    set and reject anything outside it — validated in the app (the table is plain
    ``text``), kept centralised so the standardised/legacy field lists are cheap to
    adjust. ``titolo`` is deliberately NOT here: it is free text (see below)."""
    assert getattr(Scheda(**{field: good}), field) == good

    with pytest.raises(ValidationError):
        Scheda(**{field: bad})


def test_titolo_accepts_free_text():
    """``titolo`` is an editable combobox in the widget: picking "altro" lets a Master
    type a custom titolo, saved verbatim. So the model accepts both a suggested value
    and any free-text value — it is not enum-validated."""
    assert Scheda(titolo="proprieta").titolo == "proprieta"
    assert Scheda(titolo="concessione demaniale").titolo == "concessione demaniale"


def test_vincoli_accepts_a_subset_of_the_allowed_set():
    """``vincoli`` is multi-valued: any subset of the allowed set is accepted (it is
    a checklist, not a single choice)."""
    assert Scheda(vincoli=["paesaggistico", "culturale"]).vincoli == [
        "paesaggistico",
        "culturale",
    ]


def test_vincoli_accepts_a_custom_member():
    """``vincoli`` accepts free-text members: the Vincoli "altro" checkbox opens an
    editable box whose text is saved as a custom member alongside the suggested ones,
    so a value outside VINCOLI_VALUES is kept, not rejected."""
    assert Scheda(vincoli=["paesaggistico", "sismico"]).vincoli == [
        "paesaggistico",
        "sismico",
    ]


def test_empty_scheda_is_valid():
    """Every Scheda field is optional/non-blocking: an empty Scheda is valid, so a
    Blueprint can be saved with the Scheda left empty (the first Load need not fill
    it). The enum-like fields are simply absent (``None``), not defaulted."""
    scheda = Scheda()

    assert scheda.titolo is None
    assert scheda.stato_uso is None
    assert scheda.condizioni is None
    assert scheda.vincoli is None
    assert scheda.denominazione is None
