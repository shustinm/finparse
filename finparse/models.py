from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

from pydantic import BaseModel


class Currency(Enum):
    ILS = "₪"
    USD = "$"
    EURO = "€"


class Transaction(BaseModel):
    date: datetime
    description: str
    amount: str
    currency: Currency
    foreign_amount: str | None = None
    foreign_currency: Currency | None = None
    category: str | None = None
    id: int | None = None
    notes: str | None = None

    def __str__(self):
        return f"{self.amount}{self.currency.value} -> {self.description} ({self.date})"


def str_transactions(transactions: list[Transaction]) -> str:
    ret = []
    for t in transactions:
        ret.append(f"\n  - {str(t)}")
    return "".join(ret)


class Card(BaseModel):
    name: str
    last_4_digits: str
    transactions: list[Transaction] = []
    enabled: bool = True

    @property
    def description(self) -> str:
        return f"{self.name} - {self.last_4_digits}{' (disabled)' if not self.enabled else ''}"

    def __str__(self):
        return (
            f"{self.description}\n"
            f"transactions: {str_transactions(self.transactions)}\n"
        )


type CardExportParser = Callable[[Path], Iterable[Card]]
