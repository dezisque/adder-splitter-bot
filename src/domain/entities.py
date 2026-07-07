from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.domain.enums import ExpenseKind, SplitType
from src.domain.value_objects import Money


@dataclass(slots=True)
class User:
    id: int
    telegram_id: int
    username: str | None
    first_name: str
    created_at: datetime


@dataclass(slots=True)
class Room:
    id: int
    title: str
    owner_user_id: int
    invite_token: str
    currency: str
    is_archived: bool
    created_at: datetime


@dataclass(slots=True)
class Participant:
    id: int
    room_id: int
    user_id: int | None
    display_name: str
    is_active: bool

    @property
    def is_virtual(self) -> bool:
        return self.user_id is None


@dataclass(frozen=True, slots=True)
class ExpenseShare:
    participant_id: int
    amount: int


@dataclass(slots=True)
class Expense:
    id: int
    room_id: int
    kind: ExpenseKind
    paid_by_participant_id: int
    amount: Money
    description: str
    split_type: SplitType
    created_by_user_id: int
    created_at: datetime
    shares: list[ExpenseShare] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Transfer:
    """Расчётный перевод «кто → кому → сколько»; в БД не хранится."""

    from_participant_id: int
    to_participant_id: int
    amount: int


@dataclass(frozen=True, slots=True)
class BalanceLine:
    participant_id: int
    paid: int
    owed: int

    @property
    def net(self) -> int:
        return self.paid - self.owed


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    lines: list[BalanceLine]
    transfers: list[Transfer]
