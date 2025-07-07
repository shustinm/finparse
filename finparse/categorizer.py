from dataclasses import dataclass
from typing import Optional

from firefly_iii_client import RuleStore, RuleTriggerStore, RuleActionStore
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from loguru import logger


@dataclass
class CategorizationResult:
    """Result of AI categorization for a merchant."""

    merchant_name: str
    category_name: str
    confidence: float
    pattern: str
    notes: Optional[str] = None


class CategorizationRequest(BaseModel):
    """Request for AI categorization."""

    merchant_name: str = Field(description="The merchant name to categorize")
    available_categories: list[str] = Field(
        description="List of available categories in Firefly III"
    )


class CategorizationResponse(BaseModel):
    """AI response for categorization."""

    category_name: str = Field(
        description="The selected category name from available_categories"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0", ge=0.0, le=1.0
    )
    pattern: str = Field(
        description="Pattern to match this merchant (e.g., exact name or partial match)"
    )
    reasoning: str = Field(
        description="Brief explanation of why this category was chosen"
    )
    notes: Optional[str] = Field(
        default=None, description="Additional notes about the categorization"
    )


class Categorizer:
    """Base class for transaction categorizers."""

    def categorize_merchant(self, merchant_name: str) -> CategorizationResult:
        """Categorize a merchant and return the result."""
        raise NotImplementedError

    def create_rule(
        self, result: CategorizationResult, rule_group_id: str = None
    ) -> RuleStore:
        """Create a Firefly III rule from a categorization result."""
        rule_kwargs = dict(
            title=f"Auto-categorize: {result.merchant_name}",
            description=f"AI-generated rule for {result.merchant_name} (confidence: {result.confidence:.2f})",
            trigger_stop=True,  # Stop processing other rules
            active=True,
            trigger="store-journal",
            rule_group_id=rule_group_id or "",
            triggers=[
                RuleTriggerStore(
                    type="description_contains",
                    value=result.pattern,
                    stop_processing=True,
                )
            ],
            actions=[
                RuleActionStore(
                    type="set_category",
                    value=result.category_name,
                )
            ],
        )
        return RuleStore(**rule_kwargs)


class PydanticAICategorizer(Categorizer):
    """PydanticAI-based categorizer using structured output."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        available_categories: list[str] = None,
    ):
        # Set up the OpenAI API key for pydantic-ai
        import os

        os.environ["OPENAI_API_KEY"] = api_key

        # Create the agent with structured output
        self.agent = Agent(
            f"openai:{model}",
            output_type=CategorizationResponse,
        )
        self.available_categories = available_categories or []

    def set_available_categories(self, categories: list[str]):
        """Set the available categories from Firefly III."""
        self.available_categories = categories

    async def categorize_merchant(self, merchant_name: str) -> CategorizationResult:
        """Categorize a merchant using PydanticAI with structured output."""
        if not self.available_categories:
            raise ValueError("Available categories must be set before categorization")

        # Create the prompt for categorization
        prompt = f"""
        You are an AI assistant that categorizes Israeli credit card transactions.
        
        Given a merchant name, you need to categorize it into one of the available categories.
        Consider the context of Israeli businesses and common transaction types.
        
        Merchant: {merchant_name}
        Available categories: {', '.join(self.available_categories)}
        
        Please categorize this merchant and provide:
        1. The most appropriate category from the available list
        2. A confidence score (0.0-1.0) based on how certain you are
        3. A pattern that can be used to match this merchant in future transactions
        4. Brief reasoning for your choice
        """

        try:
            result = await self.agent.run(prompt)

            return CategorizationResult(
                merchant_name=merchant_name,
                category_name=result.output.category_name,
                confidence=result.output.confidence,
                pattern=result.output.pattern,
                notes=result.output.reasoning,
            )

        except Exception as e:
            logger.error(f"Error categorizing {merchant_name}: {e}")
            # Return a fallback categorization
            return CategorizationResult(
                merchant_name=merchant_name,
                category_name="Uncategorized",
                confidence=0.0,
                pattern=merchant_name,
                notes=f"Error during categorization: {e}",
            )
