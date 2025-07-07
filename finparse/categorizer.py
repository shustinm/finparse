from dataclasses import dataclass
from typing import Optional

from firefly_iii_client import RuleStore, RuleTriggerStore, RuleActionStore


@dataclass
class CategorizationResult:
    """Result of AI categorization for a merchant."""

    merchant_name: str
    category_name: str
    confidence: float
    pattern: str
    notes: Optional[str] = None


class Categorizer:
    """Base class for transaction categorizers."""

    def categorize_merchant(self, merchant_name: str) -> CategorizationResult:
        """Categorize a merchant and return the result."""
        raise NotImplementedError

    def create_rule(self, result: CategorizationResult) -> RuleStore:
        """Create a Firefly III rule from a categorization result."""
        return RuleStore(
            title=f"Auto-categorize: {result.merchant_name}",
            description=f"AI-generated rule for {result.merchant_name} (confidence: {result.confidence:.2f})",
            trigger_stop=True,  # Stop processing other rules
            active=True,
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
