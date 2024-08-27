import inspect
from datetime import datetime
from pathlib import Path
from pprint import pformat

from firefly_iii_client import (
    TransactionSplitStore,
    TransactionTypeProperty,
    TransactionsApi,
    AccountTypeFilter,
    TransactionStore,
)
from loguru import logger
from pick import pick

from cards.isracard import parse_workbook as parse_isracard_workbook
from cards.cal import parse_workbook as parse_cal_workbook
from finparse.firefly import Firefly
from finparse.models import Card, CardExportParser, Transaction
from log import configure_log
import xattr
import typer

app = typer.Typer()


CARD_MODULE_MAPPING: dict[str, CardExportParser] = {
    "isracard.co.il": parse_isracard_workbook,
    "cal-online.co.il": parse_cal_workbook,
}


def get_download_url(
    path: Path, attr: str = "com.apple.metadata:kMDItemWhereFroms"
) -> str | None:
    # noinspection PyBroadException
    try:
        dl_link: bytes = xattr.getxattr(path, attr)
        return dl_link.decode("utf-8", "ignore")
    except Exception:
        logger.debug(f"Unable to find source of {path}", exc_info=True)
        return None


def find_parser(path: Path) -> CardExportParser:
    dl_url = get_download_url(path)
    for k, v in CARD_MODULE_MAPPING.items():
        if k in dl_url:
            return v

    raise ValueError("Couldn't find an appropriate parser")


@app.callback()
def setup(
    verbose: bool = typer.Option(False),
):
    configure_log(verbose)


def upload_transaction(transaction: Transaction, firefly: Firefly, account_id: str):
    transaction_store = TransactionSplitStore(
        amount=transaction.amount,
        var_date=datetime.combine(transaction.date, datetime.min.time()),
        description=transaction.description,
        currency_code=transaction.currency.name,
        foreign_amount=transaction.foreign_amount,
        foreign_currency_code=transaction.foreign_currency.name,
        source_id=account_id,
        type=TransactionTypeProperty.WITHDRAWAL,
    )

    firefly.transactions_api.store_transaction(
        TransactionStore(transactions=[transaction_store])
    )


def upload_card(card: Card, firefly: Firefly, account_id: str):
    for transaction in card.transactions:
        logger.info(f"Transaction: {transaction}")
        upload_transaction(transaction, firefly, account_id)


@app.command()
def upload(
    report_file: Path = typer.Argument(help="Credit card monthly report"),
    token: str = typer.Option(envvar="FINPARSE_TOKEN", help="Firefly III API token"),
    firefly_host: str = typer.Option(
        "http://localhost/api",
        envvar="FINPARSE_FIREFLY_HOST",
        help="Firefly III API host",
    ),
):
    parser: CardExportParser = find_parser(report_file)
    card_company = Path(inspect.getfile(parser)).stem.capitalize()
    logger.success(f"Found appropriate parser: {card_company}")
    cards = parser(report_file)
    logger.success(f"Done parsing cards in {report_file}, starting upload...")

    firefly = Firefly(firefly_host, token)

    accounts = firefly.accounts_api.list_account(type=AccountTypeFilter.ASSET).data
    logger.info(f"Detected {len(accounts)} asset accounts")

    # acc_name, acc_idx = pick(
    #     [acc.attributes.name for acc in accounts], title="Select Account"
    # )
    #
    # logger.success(f"Selected account: {acc_name}")
    #
    # for card in filter(lambda c: c.enabled, cards):
    #     if card.transactions:
    #         logger.info(f"Uploading transactions for {card.description}")
    #         upload_card(card, firefly.transactions_api, accounts[acc_idx].id)
    #         logger.success(f"Finished uploading {card.description}")
    #     else:
    #         logger.info(f"Card {card.description} has no transactions")
    #
    # logger.success("Finished uploading transactions from all cards")


if __name__ == "__main__":
    app()
