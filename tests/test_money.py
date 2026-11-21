from decimal import Decimal

import pytest

from app.money import parse_amount, parse_split, split_amount


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1500", Decimal("1500.00")),
        ("1 500,5", Decimal("1500.50")),
        ("0.01", Decimal("0.01")),
        ("2 000", Decimal("2000.00")),
    ],
)
def test_parse_amount_valid(text, expected):
    assert parse_amount(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "0", "-10", "1.001", "nan", "inf", "99999999"])
def test_parse_amount_invalid(text):
    assert parse_amount(text) is None


def test_parse_split():
    assert parse_split("A:40, B:40, C:20") == [("A", 40), ("B", 40), ("C", 20)]


@pytest.mark.parametrize("spec", ["A:50,B:40", "A:x", ":100", ""])
def test_parse_split_invalid(spec):
    with pytest.raises(ValueError):
        parse_split(spec)


def test_split_adds_up_exactly():
    parts = [("A", 33), ("B", 33), ("C", 34)]
    for total in [Decimal("100.00"), Decimal("0.01"), Decimal("1234.57"), Decimal("999999.99")]:
        shares = split_amount(total, parts)
        assert sum(s for _, s in shares) == total
        assert all(s == s.quantize(Decimal("0.01")) for _, s in shares)


def test_split_default_ratios():
    shares = dict(split_amount(Decimal("1000.00"), [("A", 40), ("B", 40), ("C", 20)]))
    assert shares == {"A": Decimal("400.00"), "B": Decimal("400.00"), "C": Decimal("200.00")}
