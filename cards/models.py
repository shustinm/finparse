from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Currency(Enum):
    ILS = "₪"
    USD = "$"
    EURO = "€"


class Transaction(BaseModel):
    date: date
    business: str
    amount: str
    currency: Currency
    foreign_amount: str | None = None
    foreign_currency: Currency | None = None
    id: int | None = None
    notes: str = ""

    def __str__(self):
        return f"{self.amount}{self.currency.value} -> {self.business} ({self.date})"


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
