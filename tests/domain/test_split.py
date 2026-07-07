import pytest

from src.domain.exceptions import InvalidInput
from src.domain.services.split import split_evenly


def test_even_division() -> None:
    assert split_evenly(300, [1, 2, 3]) == {1: 100, 2: 100, 3: 100}


def test_remainder_goes_to_lowest_ids() -> None:
    # 2450 ₽ на троих: 245000 копеек -> 81667 + 81667 + 81666
    assert split_evenly(245_000, [3, 1, 2]) == {1: 81_667, 2: 81_667, 3: 81_666}


def test_sum_invariant() -> None:
    shares = split_evenly(1000, list(range(1, 8)))
    assert sum(shares.values()) == 1000


def test_single_participant() -> None:
    assert split_evenly(999, [42]) == {42: 999}


@pytest.mark.parametrize("amount", [0, -100])
def test_non_positive_amount(amount: int) -> None:
    with pytest.raises(InvalidInput):
        split_evenly(amount, [1])


def test_empty_participants() -> None:
    with pytest.raises(InvalidInput):
        split_evenly(100, [])


def test_duplicate_participants() -> None:
    with pytest.raises(InvalidInput):
        split_evenly(100, [1, 1, 2])
