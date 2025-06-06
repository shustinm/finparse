from collections.abc import Generator

import pytest
from firefly_iii_client import AccountTypeFilter
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

from finparse.firefly import Firefly, paginate


class FireflySettings(BaseSettings):
    token: str
    host: str = "http://localhost/api"

    model_config = ConfigDict(env_prefix="FINPARSE_")


@pytest.fixture
def firefly_settings() -> FireflySettings:
    """Load Firefly III settings from environment variables."""
    return FireflySettings()


@pytest.fixture
def firefly(firefly_settings: FireflySettings) -> Generator[Firefly, None, None]:
    """Create a Firefly III client instance."""
    if not firefly_settings.token:
        pytest.skip("FINPARSE_TOKEN environment variable not set")

    client = Firefly(firefly_settings.host, firefly_settings.token)
    yield client


def test_paginate_accounts(firefly: Firefly):
    """Test that pagination correctly fetches all asset accounts."""
    # Test pagination of accounts
    accounts = list(paginate(firefly.accounts_api.list_account, type=AccountTypeFilter.ASSET))

    # Verify we got some accounts
    assert len(accounts) > 0

    # Verify each account has the required fields
    for account in accounts:
        assert hasattr(account, "id")
        assert hasattr(account, "attributes")
        assert hasattr(account.attributes, "name")
        assert hasattr(account.attributes, "type")
        assert account.attributes.type == "asset"
