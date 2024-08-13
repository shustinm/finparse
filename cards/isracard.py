from datetime import datetime
from pathlib import Path
from typing import Iterable

from cards.models import Transaction, Card

from loguru import logger
import xlrd
from xlrd.sheet import Sheet
from xlrd.book import Book


def _iter_transactions(sheet: Sheet, start_row: int) -> Iterable[tuple[list, int]]:
    row = start_row

    while sheet.cell_value(row, 0) and not (
        # The last row has a date, but is a "total" footer
        sheet.cell_value(row, 1).startswith("סך חיוב")
        and sheet.cell_value(row, 1).endswith(":")
    ):
        yield sheet.row(row), row
        row += 1

    # Foreign transactions can have multiple sections (1 per foreign currency), so we do this dirty recursion
    if sheet.cell_value(row, 2) == "TOTAL FOR DATE" and sheet.cell_value(row + 1, 0):
        yield from _iter_transactions(sheet, row + 1)


def parse_local_transactions(
    sheet: Sheet, starting_idx: int
) -> tuple[list[Transaction], int]:
    row_idx = starting_idx
    transactions = []

    for row, row_idx in _iter_transactions(sheet, row_idx):
        (
            _date,
            business,
            amount,
            currency,
            debit_amount,
            debit_currency,
            _id,
            notes,
        ) = list(map(lambda c: c.value, row))

        transactions.append(
            Transaction(
                date=datetime.strptime(_date, "%d/%m/%Y").date(),
                business=business,
                amount=str(amount),
                currency=currency,
                foreign_amount=str(debit_amount),
                foreign_currency=debit_currency,
                id=_id,
                notes=notes,
            )
        )

    return transactions, row_idx + 1


def parse_foreign_transactions(sheet: Sheet, start_row: int):
    row_idx = start_row
    transactions = []

    for row, row_idx in _iter_transactions(sheet, row_idx):
        (
            _date,
            _,
            business,
            foreign_amount,
            foreign_currency,
            amount,
            currency,
            _,
        ) = list(map(lambda c: c.value, row))

        transactions.append(
            Transaction(
                date=datetime.strptime(_date, "%d/%m/%Y").date(),
                business=business,
                amount=str(amount),
                currency=currency,
                foreign_amount=str(foreign_amount),
                foreign_currency=foreign_currency,
            )
        )

    return transactions, row_idx + 1


def parse_card(sheet: Sheet, starting_idx: int) -> tuple[Card, int]:
    row = starting_idx
    card_data = {}
    card_header: str = sheet.cell_value(row, 0)

    if card_header.endswith("*"):
        card_header = card_header.removesuffix(" *")
        card_data["enabled"] = False

    name, last_4_digits = card_header.split(" - ")
    card = Card(name=name, last_4_digits=last_4_digits)

    row += 1
    while cell_value := sheet.cell_value(row, 0):
        if cell_value.startswith("עסקאות בארץ"):
            transactions, row = parse_local_transactions(sheet, row + 2)
            card.transactions.extend(transactions)
        elif cell_value.startswith("עסקאות בח"):
            transactions, row = parse_foreign_transactions(sheet, row + 2)
            card.transactions.extend(transactions)
        else:
            logger.debug(f"Skipping cell value: {cell_value}")
            break

        row += 1

    return card, row


def parse_workbook(workbook_path: Path) -> list[Card]:
    book: Book = xlrd.open_workbook(workbook_path)
    sh: Sheet = book.sheet_by_index(0)
    cards: list[Card] = []

    # Skip first row which is empty
    curr_row = 1

    logger.info(f"Parsing card for {sh.cell_value(curr_row, 0)}")
    # Skip empty row after name
    curr_row += 1

    while curr_row < sh.nrows:

        if (first := sh.cell_value(curr_row, 0)) and " - " in first:
            logger.info(f"Parsing card (row {curr_row}) for: {first}")
            card, curr_row = parse_card(sh, curr_row)
            cards.append(card)
            logger.debug(f"Ended at ({curr_row}, 0): {sh.cell_value(curr_row, 0)}")

        curr_row += 1

    return cards
