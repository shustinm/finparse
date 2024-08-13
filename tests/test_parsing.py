from pathlib import Path

import pytest

from finparse.cards import isracard, cal

FILES_PATH = Path(__file__).parent / "files"

ISRACARD_EXPORT_FOLDER = FILES_PATH / "isracard"

ISRACARD_EXPECTED_TRANSACTIONS = {
    ISRACARD_EXPORT_FOLDER / "isracard1.xls": 20,
    ISRACARD_EXPORT_FOLDER / "isracard2.xls": 23,
    ISRACARD_EXPORT_FOLDER / "isracard3.xls": 18,
}

CAL_EXPORT_FOLDER = FILES_PATH / "cal"

CAL_EXPECTED_TRANSACTIONS = {
    CAL_EXPORT_FOLDER / "cal1.xlsx": 41,
}


@pytest.mark.parametrize(
    "workbook_path, expected_transactions",
    [(k, v) for k, v in ISRACARD_EXPECTED_TRANSACTIONS.items()],
)
def test_isracard_parser(workbook_path: Path, expected_transactions: int):
    cards = isracard.parse_workbook(workbook_path)
    assert sum(len(c.transactions) for c in cards) == expected_transactions


@pytest.mark.parametrize(
    "workbook_path, expected_transactions",
    [(k, v) for k, v in CAL_EXPECTED_TRANSACTIONS.items()],
)
def test_cal_parser(workbook_path: Path, expected_transactions: int):
    cards = cal.parse_workbook(workbook_path)
    assert sum(len(c.transactions) for c in cards) == expected_transactions
