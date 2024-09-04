from enum import Enum
from typing import Self

from firefly_iii_client import (
    RuleGroupStore,
    RuleRead,
)
from loguru import logger
import firefly_iii_client as firefly3
from pydantic import BaseModel


class CategoryRule(BaseModel):
    id: str
    activators: list[str] = []

    @classmethod
    def from_rule(cls, rule: RuleRead) -> Self:
        """
        Create a CategoryRule from a rule that sets a category based on the transaction description
        """
        return cls(
            id=rule.id,
            # This assumes that all triggers are of type DESCRIPTION_* (like DESCRIPTION_IS)
            activators=[trigger.value for trigger in rule.attributes.triggers],
        )


class CategoryRuleType(Enum):
    DescriptionRule = "Finparse: Description Rules"
    TranslationRule = "Finparse: Category Translations"


class Category(BaseModel):
    id: str
    name: str

    # Description rules set the category based on the description of the transaction
    description_rules: list[CategoryRule] = []

    # Translation rules set the category based on the category written in the credit card report
    translation_rules: list[CategoryRule] = []

    def add_rule(self, rule_type: CategoryRuleType, rule: RuleRead):
        rule_obj = CategoryRule.from_rule(rule)
        logger.debug(
            f"Saving rule: {rule_type.name}: {rule_obj.activators} -> {self.name}"
        )
        match rule_type:
            case CategoryRuleType.DescriptionRule:
                self.description_rules.append(rule_obj)
            case CategoryRuleType.TranslationRule:
                self.translation_rules.append(rule_obj)


class Categories:

    def __init__(
        self,
        categories_api: firefly3.CategoriesApi,
        rule_group_api: firefly3.RuleGroupsApi,
    ):
        self.by_id: dict[str, Category] = {}
        self.id_by_name: dict[str, str] = {}

        self.categories_api = categories_api

        for firefly_category in self.categories_api.list_category().data:
            self[firefly_category.id] = Category(
                id=firefly_category.id, name=firefly_category.attributes.name
            )
        logger.success(f"Found categories: {list(self.id_by_name.keys())}")

        self.rule_groups_api = rule_group_api
        self._init_rule_group()

    def _init_rule_group(self):
        rule_groups = self.rule_groups_api.list_rule_group()

        required_rule_groups = set(rule_group for rule_group in CategoryRuleType)

        for rg in rule_groups.data:
            try:
                category_rule_type = CategoryRuleType(rg.attributes.title)
                required_rule_groups.remove(category_rule_type)
            except ValueError:
                continue

            logger.info(f"Found rule group {category_rule_type.value!r}")

            for rule in self.rule_groups_api.list_rule_by_group(rg.id).data:
                rule_category = rule.attributes.actions[0].value
                self[rule_category].add_rule(category_rule_type, rule)

        logger.info(f"Creating rule groups: {required_rule_groups}")
        for rg in required_rule_groups:
            self.rule_groups_api.store_rule_group(
                RuleGroupStore(
                    active=True,
                    title=rg.value,
                )
            )

    def get(self, name: str) -> Category | None:
        return self.by_id.get(self.id_by_name.get(name))

    def __getitem__(self, name: str):
        return self.by_id[self.id_by_name[name]]

    def __setitem__(self, key, value: Category):
        self.id_by_name[value.name] = value.id
        self.by_id[value.id] = value

    def __iter__(self):
        yield from zip(self.id_by_name, self.by_id.values())

    def __len__(self):
        return len(self.by_id)

    def __contains__(self, item):
        return item in self.id_by_name


class Firefly:
    def __init__(self, firefly_host: str, token: str):
        configuration = firefly3.configuration.Configuration(
            host=firefly_host, access_token=token
        )
        self.client = firefly3.ApiClient(configuration)

        about = firefly3.AboutApi(self.client).get_about()
        logger.success(
            f"Connected to Firefly III at {self.client.configuration.host.removesuffix('/api')}"
        )
        logger.info(
            f"Detected Firefly III version: {about.data.version} (API version: {about.data.api_version})"
        )

        self.accounts_api = firefly3.AccountsApi(self.client)
        self.transactions_api = firefly3.TransactionsApi(self.client)

        self.categories_api = firefly3.CategoriesApi(self.client)
        self.rule_groups_api = firefly3.RuleGroupsApi(self.client)

        self.categories = Categories(self.categories_api, self.rule_groups_api)
        logger.success(f"Loaded {len(self.categories)} categories")

        self.rules_api = firefly3.RulesApi(self.client)
