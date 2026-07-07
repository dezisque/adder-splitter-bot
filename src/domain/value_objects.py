from __future__ import annotations

from dataclasses import dataclass

_CURRENCY_SYMBOLS = {"RUB": "₽"}


@dataclass(frozen=True, slots=True)
class Money:
    """Денежная сумма в минорных единицах (копейках)."""

    amount: int
    currency: str = "RUB"

    def __add__(self, other: Money) -> Money:
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._ensure_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def _ensure_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError(f"валюты не совпадают: {self.currency} и {other.currency}")

    def format(self) -> str:
        major, minor = divmod(abs(self.amount), 100)
        sign = "-" if self.amount < 0 else ""
        grouped = f"{major:,}".replace(",", " ")
        symbol = _CURRENCY_SYMBOLS.get(self.currency, self.currency)
        if minor:
            return f"{sign}{grouped},{minor:02d} {symbol}"
        return f"{sign}{grouped} {symbol}"
