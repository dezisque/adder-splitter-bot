import pytest

from src.domain.exceptions import InvalidInput
from src.presentation.bot.utils import is_amount_only, parse_amount, parse_quick_expense


def test_simple() -> None:
    assert parse_quick_expense("Мясо 2450") == ("Мясо", 245_000)


def test_decimal_and_currency_word() -> None:
    assert parse_quick_expense("мясо и уголь 2 450,50 руб") == ("мясо и уголь", 245_050)


def test_ruble_sign() -> None:
    assert parse_quick_expense("Шашлык 300₽") == ("Шашлык", 30_000)


def test_number_inside_description() -> None:
    assert parse_quick_expense("Такси 2 человека 500") == ("Такси 2 человека", 50_000)


def test_no_amount() -> None:
    assert parse_quick_expense("Просто мясо") == ("Просто мясо", None)


def test_huge_amount_raises() -> None:
    with pytest.raises(InvalidInput):
        parse_quick_expense("Яхта 999999999999")


def test_is_amount_only() -> None:
    assert is_amount_only("2450")
    assert is_amount_only("2 450,50")
    assert not is_amount_only("Мясо 2450")
    assert not is_amount_only("Мясо")


@pytest.mark.parametrize("raw", ["2450", "2450.5", "2 450,50"])
def test_parse_amount_variants(raw: str) -> None:
    assert parse_amount(raw) > 0
