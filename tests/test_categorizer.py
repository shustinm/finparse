import pytest
from unittest.mock import AsyncMock, patch
from finparse.categorizer import (
    PydanticAICategorizer,
    CategorizationResult,
    CategorizationResponse,
)


@pytest.fixture
def mock_agent():
    """Mock agent for testing."""
    with patch("finparse.categorizer.Agent") as mock_agent_class:
        mock_agent = AsyncMock()
        mock_agent_class.return_value = mock_agent
        yield mock_agent


@pytest.fixture
def categorizer(mock_agent):
    """Create a categorizer instance for testing."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
        return PydanticAICategorizer(
            api_key="test-key",
            model="gpt-4o-mini",
            available_categories=["Food", "Transport", "Shopping", "Entertainment"],
        )


class TestPydanticAICategorizer:
    """Test the PydanticAI categorizer implementation."""

    def test_init(self, mock_agent):
        """Test categorizer initialization."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            categorizer = PydanticAICategorizer(api_key="test-key", model="gpt-4o-mini")

            assert categorizer.available_categories == []
            assert categorizer.agent == mock_agent

    def test_set_available_categories(self, categorizer):
        """Test setting available categories."""
        categories = ["Food", "Transport", "Shopping"]
        categorizer.set_available_categories(categories)
        assert categorizer.available_categories == categories

    @pytest.mark.asyncio
    async def test_categorize_merchant_success(self, categorizer, mock_agent):
        """Test successful merchant categorization."""
        # Mock the agent response
        mock_result = AsyncMock()
        mock_result.output = CategorizationResponse(
            category_name="Food",
            confidence=0.9,
            pattern="McDonald's",
            reasoning="Fast food restaurant",
        )
        mock_agent.run.return_value = mock_result

        result = await categorizer.categorize_merchant("McDonald's")

        assert isinstance(result, CategorizationResult)
        assert result.merchant_name == "McDonald's"
        assert result.category_name == "Food"
        assert result.confidence == 0.9
        assert result.pattern == "McDonald's"
        assert result.notes == "Fast food restaurant"

        # Verify the agent was called with the correct prompt
        mock_agent.run.assert_called_once()
        call_args = mock_agent.run.call_args[0][0]
        assert "McDonald's" in call_args
        assert "Food" in call_args
        assert "Transport" in call_args

    @pytest.mark.asyncio
    async def test_categorize_merchant_no_categories(self, categorizer):
        """Test categorization without available categories."""
        categorizer.available_categories = []

        with pytest.raises(ValueError, match="Available categories must be set"):
            await categorizer.categorize_merchant("Test Merchant")

    @pytest.mark.asyncio
    async def test_categorize_merchant_error(self, categorizer, mock_agent):
        """Test categorization when agent raises an error."""
        mock_agent.run.side_effect = Exception("API Error")

        result = await categorizer.categorize_merchant("Test Merchant")

        assert isinstance(result, CategorizationResult)
        assert result.merchant_name == "Test Merchant"
        assert result.category_name == "Uncategorized"
        assert result.confidence == 0.0
        assert result.pattern == "Test Merchant"
        assert "Error during categorization" in result.notes

    def test_create_rule(self, categorizer):
        """Test rule creation."""
        result = CategorizationResult(
            merchant_name="McDonald's",
            category_name="Food",
            confidence=0.9,
            pattern="McDonald's",
            notes="Fast food restaurant",
        )

        rule = categorizer.create_rule(result, rule_group_id="test-group")

        assert rule.title == "Auto-categorize: McDonald's"
        assert rule.description == "AI-generated rule for McDonald's (confidence: 0.90)"
        assert rule.active is True
        assert rule.rule_group_id == "test-group"
        assert rule.trigger == "store-journal"
        # Check triggers
        assert len(rule.triggers) == 1
        trigger = rule.triggers[0]
        assert trigger.type == "description_contains"
        assert trigger.value == "McDonald's"
        assert trigger.stop_processing is True
        # Check actions
        assert len(rule.actions) == 1
        action = rule.actions[0]
        assert action.type == "set_category"
        assert action.value == "Food"

    def test_create_rule_no_group(self, categorizer):
        """Test rule creation without rule group."""
        result = CategorizationResult(
            merchant_name="McDonald's",
            category_name="Food",
            confidence=0.9,
            pattern="McDonald's",
            notes="Fast food restaurant",
        )

        rule = categorizer.create_rule(result)
        assert rule.rule_group_id == ""
