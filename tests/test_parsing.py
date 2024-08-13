from pathlib import Path

import pytest

from finparse.cards.isracard import parse_workbook

ISRACARD_EXPORT_FOLDER = Path(__file__).parent / "files" / "isracard"

EXPORT_EXPECTED_TRANSACTIONS = {
    ISRACARD_EXPORT_FOLDER / "isracard1.xls": 20,
    ISRACARD_EXPORT_FOLDER / "isracard2.xls": 23,
    ISRACARD_EXPORT_FOLDER / "isracard3.xls": 18,
}


@pytest.mark.parametrize(
    "workbook_path, expected_transactions",
    [(k, v) for k, v in EXPORT_EXPECTED_TRANSACTIONS.items()],
)
def test_isracard_parser(workbook_path: Path, expected_transactions: int):
    cards = parse_workbook(workbook_path)
    assert sum(len(c.transactions) for c in cards) == expected_transactions
