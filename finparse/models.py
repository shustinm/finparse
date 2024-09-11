from abc import ABC, abstractmethod
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
    id: str | None = None
    notes: str | None = None

    def __str__(self):
        return f"{self.amount}{self.currency.value} -> {self.description} ({self.date})"

    @property
    def firefly_notes(self) -> dict:
        d = {}
        if self.category:
            d["Reported Category"] = self.category
        return d


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
        return f"{self.name} - {self.last_4_digits}"

    def __str__(self):
        return (
            f"{self.description}\n"
            f"transactions: {str_transactions(self.transactions)}\n"
        )


class ReportParser(ABC):
    @staticmethod
    @abstractmethod
    def parse_workbook(workbook_path: Path) -> Iterable[Card]: ...

    @staticmethod
    def get_category_translations() -> dict[str, str]:
        return {}
