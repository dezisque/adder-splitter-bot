import pytest

from src.domain.entities import Transfer
from src.domain.services.settlement import simplify_debts


def test_example_from_spec() -> None:
    # Игорь(1) потратил 4500 ₽, Маша(2) 1200 ₽, Данил(3) 800 ₽, делится на всех.
    # Доли: 216667 + 216667 + 216666 копеек.
    nets = {1: 233_333, 2: -96_667, 3: -136_666}
    assert simplify_debts(nets) == [
        Transfer(3, 1, 136_666),
        Transfer(2, 1, 96_667),
    ]


def test_zero_balances() -> None:
    assert simplify_debts({1: 0, 2: 0}) == []


def test_settled_pair_skipped() -> None:
    nets = {1: -100, 2: 0, 3: 100}
    assert simplify_debts(nets) == [Transfer(1, 3, 100)]


def test_transfers_bounded_by_n_minus_1() -> None:
    nets = {1: 500, 2: -100, 3: -100, 4: -100, 5: -100, 6: -100}
    transfers = simplify_debts(nets)
    assert len(transfers) <= 5
    assert sum(t.amount for t in transfers) == 500
    assert all(t.to_participant_id == 1 for t in transfers)


def test_split_creditor() -> None:
    # Один долг закрывает двух кредиторов двумя переводами.
    nets = {1: 60, 2: 40, 3: -100}
    assert simplify_debts(nets) == [Transfer(3, 1, 60), Transfer(3, 2, 40)]


def test_nonzero_sum_raises() -> None:
    with pytest.raises(ValueError):
        simplify_debts({1: 100})
