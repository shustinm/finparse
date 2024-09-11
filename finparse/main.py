import inspect
from datetime import datetime
from pathlib import Path
from typing import Type

from firefly_iii_client import (
    TransactionSplitStore,
    TransactionTypeProperty,
    AccountTypeFilter,
    TransactionStore,
)
from loguru import logger
from pick import pick

from cards.isracard import IsracardReportParser
from cards.cal import CalReportParser
from finparse.firefly import Firefly
from finparse.models import Card, Transaction, ReportParser
from log import configure_log
import xattr
import typer

app = typer.Typer()


CARD_MODULE_MAPPING: dict[str, Type[ReportParser]] = {
    "isracard.co.il": IsracardReportParser,
    "cal-online.co.il": CalReportParser,
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


def find_parser(path: Path) -> Type[ReportParser]:
    dl_url = get_download_url(path)
    for k, v in CARD_MODULE_MAPPING.items():
        if k in dl_url:
            return v

    raise ValueError("Couldn't find an appropriate parser")


@app.callback()
def setup(verbose: bool = typer.Option(False)):
    configure_log(verbose)


def generate_notes_str(**notes) -> str:
    return ";\n".join(f"{k}: {v}" for k, v in notes.items())


def upload_transaction(
    transaction: Transaction,
    card: Card,
    firefly: Firefly,
    parser: Type[ReportParser],
    account_id: str,
):
    transaction_store = TransactionSplitStore(
        amount=transaction.amount,
        var_date=datetime.combine(transaction.date, datetime.min.time()),
        description=transaction.description,
        category_name=parser.get_category_translations().get(transaction.category),
        currency_code=transaction.currency.name,
        external_id=transaction.id,
        foreign_amount=transaction.foreign_amount,
        foreign_currency_code=transaction.foreign_currency.name,
        source_id=account_id,
        type=TransactionTypeProperty.WITHDRAWAL,
        notes=generate_notes_str(**transaction.firefly_notes),
        tags=[card.description],
    )

    firefly.transactions_api.store_transaction(
        TransactionStore(transactions=[transaction_store])
    )


def upload_card(
    card: Card, firefly: Firefly, parser: Type[ReportParser], account_id: str
):
    for transaction in card.transactions:
        logger.info(f"Transaction: {transaction}")
        upload_transaction(transaction, card, firefly, parser, account_id)


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
    parser = find_parser(report_file)
    card_company = Path(inspect.getfile(parser)).stem.capitalize()
    logger.success(f"Found appropriate parser: {card_company}")
    cards = parser.parse_workbook(report_file)
    logger.success(f"Done parsing cards in {report_file}, starting upload...")

    firefly = Firefly(firefly_host, token)

    accounts = firefly.accounts_api.list_account(type=AccountTypeFilter.ASSET).data
    logger.info(f"Detected {len(accounts)} asset accounts")

    acc_name, acc_idx = pick(
        tuple(acc.attributes.name for acc in accounts), title="Select Account"
    )

    logger.success(f"Selected account: {acc_name}")

    card: Card
    for card in filter(lambda c: c.enabled, cards):
        if card.transactions:
            logger.info(f"Uploading transactions for {card.description}")
            upload_card(
                card,
                firefly,
                parser,
                accounts[acc_idx].id,
            )
            logger.success(f"Finished uploading {card.description}")
        else:
            logger.info(f"Card {card.description} has no transactions")

    logger.success("Finished uploading transactions from all cards")


if __name__ == "__main__":
    app()
