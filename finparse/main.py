import itertools
from datetime import datetime
from pathlib import Path

import firefly_iii_client as firefly3
from firefly_iii_client import (
    TransactionSplitStore,
    TransactionTypeProperty,
    ApiClient,
    TransactionsApi,
)
from loguru import logger
from pick import pick

from cards.isracard import parse_workbook
from cards.models import Card
from log import configure_log
import xattr
import typer

app = typer.Typer()

firefly_client: ApiClient | None = None


def get_download_url(
    path: Path, attr: str = "com.apple.metadata:kMDItemWhereFroms"
) -> str | None:
    # noinspection PyBroadException
    try:
        dl_link: bytes = xattr.getxattr(path, attr)
        logger.debug(f"{path} attribute {attr}: {dl_link}")
        return dl_link.decode("utf-8", "ignore")
    except Exception:
        logger.debug(f"Unable to find source of {path}", exc_info=True)
        return None


@app.callback()
def setup(
    verbose: bool = typer.Option(False),
    token: str = typer.Option(envvar="FINPARSE_TOKEN", help="Firefly III API token"),
    firefly_host: str = typer.Option(
        "http://localhost/api",
        envvar="FINPARSE_FIREFLY_HOST",
        help="Firefly III API host",
    ),
):
    configure_log(verbose)
    firefly_setup(token, firefly_host)


def firefly_setup(token: str, firefly_host: str):
    global firefly_client

    configuration = firefly3.configuration.Configuration(
        host=firefly_host, access_token=token
    )
    firefly_client = firefly3.ApiClient(configuration)

    about = firefly3.AboutApi(firefly_client).get_about()
    logger.success(
        f"Connected to Firefly III at {firefly_client.configuration.host.removesuffix('/api')}"
    )
    logger.info(
        f"Detected Firefly III version: {about.data.version} (API version: {about.data.api_version})"
    )


def upload_card(card: Card, transactions_api: TransactionsApi, account_id: str):
    for transaction in card.transactions:
        logger.info(f"Transaction: {transaction}")
        transaction_store = TransactionSplitStore(
            amount=transaction.amount,
            var_date=datetime.combine(transaction.date, datetime.min.time()),
            description=transaction.business,
            currency_code=transaction.currency.name,
            foreign_amount=transaction.foreign_amount,
            foreign_currency_code=transaction.foreign_currency.name,
            source_id=account_id,
            type=TransactionTypeProperty.WITHDRAWAL,
        )

        transactions_api.store_transaction(
            firefly3.TransactionStore(transactions=[transaction_store])
        )


@app.command()
def upload(report_file: Path = typer.Argument(help="Credit card monthly report")):
    cards = parse_workbook(report_file)
    logger.success(f"Done parsing cards in {report_file}")
    d = get_download_url(report_file)
    logger.debug(d)

    accounts = (
        firefly3.AccountsApi(firefly_client)
        .list_account(type=firefly3.AccountTypeFilter.ASSET)
        .data
    )
    logger.info(f"Detected {len(accounts)} asset accounts")

    acc_name, acc_idx = pick(
        [acc.attributes.name for acc in accounts], title="Select Account"
    )

    logger.success(f"Selected account: {acc_name}")
    transaction_api = firefly3.TransactionsApi(firefly_client)

    for card in filter(lambda c: c.enabled, cards):
        logger.info(f"Uploading transactions for {card.description}")
        upload_card(card, transaction_api, accounts[acc_idx].id)
        logger.success(f"Finished working on {card.description}")


if __name__ == "__main__":
    app()
