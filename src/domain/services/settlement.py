from collections.abc import Mapping

from src.domain.entities import Transfer


def simplify_debts(nets: Mapping[int, int]) -> list[Transfer]:
    """Сводит чистые балансы участников (net = paid - owed) к списку переводов.

    Жадная стратегия: самый крупный должник платит самому крупному кредитору.
    Даёт не более n - 1 переводов, детерминирована (tie-break по меньшему id).
    """
    if sum(nets.values()) != 0:
        raise ValueError("сумма чистых балансов должна быть нулевой")

    debtors = [(pid, -net) for pid, net in nets.items() if net < 0]
    creditors = [(pid, net) for pid, net in nets.items() if net > 0]

    def _largest(items: list[tuple[int, int]]) -> int:
        return max(range(len(items)), key=lambda i: (items[i][1], -items[i][0]))

    transfers: list[Transfer] = []
    while debtors and creditors:
        di = _largest(debtors)
        ci = _largest(creditors)
        debtor_id, debt = debtors[di]
        creditor_id, credit = creditors[ci]
        paid = min(debt, credit)
        transfers.append(Transfer(debtor_id, creditor_id, paid))
        if debt == paid:
            debtors.pop(di)
        else:
            debtors[di] = (debtor_id, debt - paid)
        if credit == paid:
            creditors.pop(ci)
        else:
            creditors[ci] = (creditor_id, credit - paid)
    return transfers
