import pytest

from coop_manager.core import DomainError
from coop_manager.core.money import format_euro, parse_euro


@pytest.mark.parametrize(
    ("text", "cents"),
    [("50", 5000), ("50,00", 5000), ("50.00", 5000), ("50,5", 5050), (" 0,07 ", 7), ("1250,99", 125099)],
)
def test_parse_euro(text, cents):
    assert parse_euro(text) == cents


@pytest.mark.parametrize("text", ["", "abc", "50,005", "-50", "50,", "1.000,00", "50 €"])
def test_parse_euro_rejects_invalid_input(text):
    with pytest.raises(DomainError, match="kein gültiger Euro-Betrag"):
        parse_euro(text)


@pytest.mark.parametrize(("cents", "text"), [(5000, "50,00 €"), (7, "0,07 €"), (0, "0,00 €"), (-5050, "-50,50 €")])
def test_format_euro(cents, text):
    assert format_euro(cents) == text
