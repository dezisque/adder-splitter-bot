from dataclasses import dataclass

from src.domain.entities import Expense, Participant, Room
from src.domain.enums import ExpenseKind


@dataclass(frozen=True, slots=True)
class RoomOverview:
    room: Room
    me: Participant
    is_owner: bool
    members_count: int
    expenses_count: int
    expenses_sum: int
    my_net: int  # личный баланс: потратил минус доля, в копейках


@dataclass(frozen=True, slots=True)
class MemberView:
    """Участник + username привязанного Telegram-аккаунта (для экрана участников)."""

    participant: Participant
    username: str | None


@dataclass(frozen=True, slots=True)
class ExpenseCard:
    expense: Expense
    room: Room
    payer: Participant
    shares: list[tuple[Participant, int]]
    author_name: str
    can_edit: bool


@dataclass(frozen=True, slots=True)
class HistoryItem:
    expense_id: int
    kind: ExpenseKind
    description: str
    amount: int


@dataclass(frozen=True, slots=True)
class HistoryPage:
    items: list[HistoryItem]
    page: int
    total_pages: int
    currency: str


@dataclass(frozen=True, slots=True)
class BalanceEntry:
    participant: Participant
    paid: int
    owed: int

    @property
    def net(self) -> int:
        return self.paid - self.owed


@dataclass(frozen=True, slots=True)
class TransferView:
    from_participant: Participant
    to_participant: Participant
    amount: int


@dataclass(frozen=True, slots=True)
class BalanceView:
    room: Room
    lines: list[BalanceEntry]
    transfers: list[TransferView]
