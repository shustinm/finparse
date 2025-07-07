import pytest
from unittest.mock import AsyncMock, patch
from firefly_iii_client import RuleStore, RuleTriggerStore, RuleActionStore

from finparse.categorizer import (
    PydanticAICategorizer,
    CategorizationResult,
    CategorizationResponse,
)
from finparse.firefly import Firefly


@pytest.fixture
def firefly_settings():
    """Load Firefly III settings from environment variables."""
    from pydantic import ConfigDict
    from pydantic_settings import BaseSettings

    class FireflySettings(BaseSettings):
        token: str
        host: str = "http://localhost"
        model_config = ConfigDict(env_prefix="FINPARSE_")

    return FireflySettings()


@pytest.fixture
def firefly(firefly_settings):
    """Create a real Firefly III client instance."""
    if not firefly_settings.token:
        pytest.skip("FINPARSE_TOKEN environment variable not set")

    # Remove trailing slash if present and append /api
    client = Firefly(f"{firefly_settings.host.rstrip('/')}/api", firefly_settings.token)
    return client


@pytest.fixture
def mock_ai_response():
    """Mock AI response for categorization."""
    return CategorizationResponse(
        category_name="Food and Beverages",
        confidence=0.9,
        pattern="McDonald's",
        reasoning="Fast food restaurant",
    )


class TestCategorizerIntegration:
    """Integration tests using real Firefly III instance with mocked AI."""

    def test_categorizer_with_real_firefly(self, firefly, mock_ai_response):
        """Test categorizer initialization with real Firefly III categories."""
        # Get real categories from Firefly III
        available_categories = list(firefly.categories.id_by_name.keys())
        assert len(available_categories) > 0, "No categories found in Firefly III"

        # Initialize categorizer with real categories
        categorizer = PydanticAICategorizer(api_key="test-key", model="gpt-4o-mini")
        categorizer.set_available_categories(available_categories)

        # Verify categories were set
        assert len(categorizer.available_categories) == len(available_categories)
        assert "Food and Beverages" in categorizer.available_categories or any(
            "food" in cat.lower() for cat in available_categories
        )

    @pytest.mark.asyncio
    async def test_categorize_merchant_with_real_categories(
        self, firefly, mock_ai_response
    ):
        """Test merchant categorization using real Firefly III categories."""
        # Get real categories
        available_categories = list(firefly.categories.id_by_name.keys())

        # Initialize categorizer
        categorizer = PydanticAICategorizer(api_key="test-key", model="gpt-4o-mini")
        categorizer.set_available_categories(available_categories)

        # Mock the AI response
        with patch.object(categorizer.agent, "run") as mock_run:
            mock_result = AsyncMock()
            mock_result.output = mock_ai_response
            mock_run.return_value = mock_result

            # Test categorization
            result = await categorizer.categorize_merchant("McDonald's")

            assert isinstance(result, CategorizationResult)
            assert result.merchant_name == "McDonald's"
            assert result.category_name == "Food and Beverages"
            assert result.confidence == 0.9
            assert result.pattern == "McDonald's"
            assert result.notes == "Fast food restaurant"

    def test_create_rule_with_real_firefly(self, firefly):
        """Test rule creation with real Firefly III rule groups."""
        # Get or create a rule group for testing
        rule_groups = firefly.rule_groups_api.list_rule_group()
        test_rule_group_id = None

        # Look for existing AI categorization group
        for rg in rule_groups.data:
            if rg.attributes.title == "Finparse: AI Categorization":
                test_rule_group_id = rg.id
                break

        # If not found, create one
        if not test_rule_group_id:
            from firefly_iii_client import RuleGroupStore

            new_group = firefly.rule_groups_api.store_rule_group(
                RuleGroupStore(
                    active=True,
                    title="Finparse: AI Categorization",
                )
            )
            test_rule_group_id = new_group.data.id

        # Test rule creation
        categorizer = PydanticAICategorizer(api_key="test-key")
        result = CategorizationResult(
            merchant_name="McDonald's",
            category_name="Food and Beverages",
            confidence=0.9,
            pattern="McDonald's",
            notes="Fast food restaurant",
        )

        rule = categorizer.create_rule(result, test_rule_group_id)

        # Verify rule structure
        assert rule.title == "Auto-categorize: McDonald's"
        assert rule.description == "AI-generated rule for McDonald's (confidence: 0.90)"
        assert rule.active is True
        assert rule.rule_group_id == test_rule_group_id
        assert rule.trigger == "store-journal"

        # Verify triggers
        assert len(rule.triggers) == 1
        trigger = rule.triggers[0]
        assert trigger.type == "description_contains"
        assert trigger.value == "McDonald's"
        assert trigger.stop_processing is True

        # Verify actions
        assert len(rule.actions) == 1
        action = rule.actions[0]
        assert action.type == "set_category"
        assert action.value == "Food and Beverages"

    @pytest.mark.asyncio
    async def test_full_categorization_workflow(self, firefly, mock_ai_response):
        """Test the complete categorization workflow with real Firefly III."""
        # Get real categories
        available_categories = list(firefly.categories.id_by_name.keys())

        # Initialize categorizer
        categorizer = PydanticAICategorizer(api_key="test-key", model="gpt-4o-mini")
        categorizer.set_available_categories(available_categories)

        # Mock AI responses for multiple merchants
        mock_responses = {
            "McDonald's": CategorizationResponse(
                category_name="Food and Beverages",
                confidence=0.9,
                pattern="McDonald's",
                reasoning="Fast food restaurant",
            ),
            "Shell": CategorizationResponse(
                category_name="Transportation",
                confidence=0.8,
                pattern="Shell",
                reasoning="Gas station",
            ),
        }

        with patch.object(categorizer.agent, "run") as mock_run:
            # Configure mock to return different responses based on merchant
            async def mock_run_side_effect(prompt):
                mock_result = AsyncMock()
                for merchant, response in mock_responses.items():
                    if merchant in prompt:
                        mock_result.output = response
                        break
                return mock_result

            mock_run.side_effect = mock_run_side_effect

            # Test categorization for multiple merchants
            for merchant_name in ["McDonald's", "Shell"]:
                result = await categorizer.categorize_merchant(merchant_name)

                assert isinstance(result, CategorizationResult)
                assert result.merchant_name == merchant_name
                assert result.confidence > 0.7  # High confidence
                assert result.category_name in available_categories

    def test_rule_storage_in_firefly(self, firefly):
        """Test that rules can actually be stored in Firefly III."""
        # Get or create rule group
        rule_groups = firefly.rule_groups_api.list_rule_group()
        test_rule_group_id = None

        for rg in rule_groups.data:
            if rg.attributes.title == "Finparse: AI Categorization":
                test_rule_group_id = rg.id
                break

        if not test_rule_group_id:
            from firefly_iii_client import RuleGroupStore

            new_group = firefly.rule_groups_api.store_rule_group(
                RuleGroupStore(
                    active=True,
                    title="Finparse: AI Categorization",
                )
            )
            test_rule_group_id = new_group.data.id

        # Create a test rule
        categorizer = PydanticAICategorizer(api_key="test-key")
        result = CategorizationResult(
            merchant_name="Test Merchant",
            category_name="Food and Beverages",
            confidence=0.9,
            pattern="Test Merchant",
            notes="Test rule for integration testing",
        )

        rule = categorizer.create_rule(result, test_rule_group_id)

        # Store the rule in Firefly III
        stored_rule = firefly.rules_api.store_rule(rule)

        # Verify the rule was stored
        assert stored_rule.data.id is not None
        assert stored_rule.data.attributes.title == "Auto-categorize: Test Merchant"
        assert stored_rule.data.attributes.active is True

        # Clean up: delete the test rule
        firefly.rules_api.delete_rule(stored_rule.data.id)
