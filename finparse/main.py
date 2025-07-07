import inspect
from datetime import datetime
from pathlib import Path

import typer
import xattr
from firefly_iii_client import (
    AccountTypeFilter,
    TransactionSplitStore,
    TransactionStore,
    TransactionTypeProperty,
)
from loguru import logger
from pick import pick

from finparse.cards.cal import CalReportParser
from finparse.cards.isracard import IsracardReportParser
from finparse.firefly import Firefly, paginate, FireflyConnectionError
from finparse.log import configure_log
from finparse.models import Card, ReportParser, Transaction
from finparse.categorizer import Categorizer, CategorizationResult

app = typer.Typer()


CARD_MODULE_MAPPING: dict[str, type[ReportParser]] = {
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


def find_parser(path: Path) -> type[ReportParser]:
    """
    Find the appropriate parser for the given report file.

    NOTE: Currently only works on MacOS, since implementation of get_download_url is MacOS-specific
    """
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
    parser: type[ReportParser],
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
    card: Card, firefly: Firefly, parser: type[ReportParser], account_id: str
):
    for transaction in card.transactions:
        logger.info(f"Transaction: {transaction}")
        upload_transaction(transaction, card, firefly, parser, account_id)


def select_account(firefly: Firefly) -> tuple[str, str]:
    """Select an account from Firefly III and return its name and ID."""
    accounts = list(
        paginate(firefly.accounts_api.list_account, type=AccountTypeFilter.ASSET)
    )
    logger.info(f"Detected {len(accounts)} asset accounts")

    acc_name, acc_idx = pick(
        tuple(acc.attributes.name for acc in accounts), title="Select Account"
    )
    logger.success(f"Selected account: {acc_name}")
    return acc_name, accounts[acc_idx].id


def process_report_file(report_file: Path, firefly: Firefly, account_id: str) -> None:
    """Process a single report file and upload its transactions."""
    parser = find_parser(report_file)
    card_company = Path(inspect.getfile(parser)).stem.capitalize()
    logger.success(f"Found appropriate parser: {card_company} for {report_file}")

    cards = parser.parse_workbook(report_file)
    logger.success(f"Done parsing cards in {report_file}, starting upload...")

    for card in filter(lambda c: c.enabled, cards):
        if card.transactions:
            logger.info(f"Uploading transactions for {card.description}")
            upload_card(card, firefly, parser, account_id)
            logger.success(f"Finished uploading {card.description}")
        else:
            logger.info(f"Card {card.description} has no transactions")

    logger.success(f"Finished uploading transactions from {report_file}")


@app.command()
def upload(
    report_files: list[Path] = typer.Argument(help="Credit card monthly report(s)"),
    token: str = typer.Option(envvar="FINPARSE_TOKEN", help="Firefly III API token"),
    firefly_host: str = typer.Option(
        "http://localhost",
        envvar="FINPARSE_FIREFLY_HOST",
        help="Firefly III API host",
    ),
):
    try:
        firefly = Firefly(f"{firefly_host.rstrip('/')}/api", token)
    except FireflyConnectionError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)

    _, account_id = select_account(firefly)

    for report_file in report_files:
        process_report_file(report_file, firefly, account_id)

    logger.success("Finished uploading transactions from all files")


@app.command()
def categorize(
    token: str = typer.Option(envvar="FINPARSE_TOKEN", help="Firefly III API token"),
    firefly_host: str = typer.Option(
        "http://localhost",
        envvar="FINPARSE_FIREFLY_HOST",
        help="Firefly III API host",
    ),
):
    """Categorize uncategorized transactions using AI-generated rules."""
    try:
        firefly = Firefly(f"{firefly_host.rstrip('/')}/api", token)
    except FireflyConnectionError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)

    # Get all transactions
    transactions = list(
        paginate(
            firefly.transactions_api.list_transaction,
        )
    )

    # Filter for uncategorized transactions
    uncategorized = [
        t for t in transactions if not t.attributes.transactions[0].category_id
    ]

    if not uncategorized:
        logger.info("No uncategorized transactions found")
        return

    logger.info(f"Found {len(uncategorized)} uncategorized transactions")

    # Group transactions by merchant name
    merchant_transactions: dict[str, list] = {}
    for transaction in uncategorized:
        description = transaction.attributes.transactions[0].description
        if description not in merchant_transactions:
            merchant_transactions[description] = []
        merchant_transactions[description].append(transaction)

    logger.info(f"Found {len(merchant_transactions)} unique merchants")

    # TODO: Initialize categorizer based on configuration
    categorizer: Categorizer = None  # type: ignore

    # Process each merchant
    for merchant_name, transactions in merchant_transactions.items():
        logger.info(f"Processing merchant: {merchant_name}")
        try:
            result = categorizer.categorize_merchant(merchant_name)

            # Only create rules for high confidence matches
            if result.confidence > 0.7:
                rule = categorizer.create_rule(result)
                firefly.rules_api.store_rule(rule)
                logger.success(
                    f"Created rule for {merchant_name} -> {result.category_name} "
                    f"(confidence: {result.confidence:.2f})"
                )
            else:
                logger.warning(
                    f"Low confidence categorization for {merchant_name}: "
                    f"{result.category_name} ({result.confidence:.2f})"
                )
        except Exception as e:
            logger.error(f"Error processing {merchant_name}: {e}")


if __name__ == "__main__":
    app()
