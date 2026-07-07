from collections.abc import Sequence

from src.domain.exceptions import InvalidInput


def split_evenly(amount: int, participant_ids: Sequence[int]) -> dict[int, int]:
    """Делит сумму поровну; остаток копеек уходит первым участникам по возрастанию id.

    Инвариант: sum(result.values()) == amount.
    """
    if amount <= 0:
        raise InvalidInput("Сумма должна быть положительной")
    ids = sorted(participant_ids)
    if not ids:
        raise InvalidInput("Нужен хотя бы один участник")
    if len(set(ids)) != len(ids):
        raise InvalidInput("Участники в делёжке не должны повторяться")
    base, remainder = divmod(amount, len(ids))
    return {pid: base + (1 if i < remainder else 0) for i, pid in enumerate(ids)}
