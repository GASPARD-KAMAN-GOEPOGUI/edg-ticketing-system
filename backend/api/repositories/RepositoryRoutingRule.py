from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelRoutingRule import RoutingRule
from api.repositories.base_repository import BaseRepository


class RoutingRuleRepository(BaseRepository[RoutingRule]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RoutingRule, session)

    async def list_ordered(self) -> list[RoutingRule]:
        """Liste toutes les règles actives triées par sort_order."""
        items, _ = await self.list(
            only_active=True,
            order_by="sort_order",
            limit=500,
        )
        return items

    async def find_by_condition(
        self, condition_field: str, condition_value: str
    ) -> RoutingRule | None:
        return await self.get_one(
            {"condition_field": condition_field, "condition_value": condition_value}
        )

    async def list_by_direction(
        self, direction_id: str
    ) -> list[RoutingRule]:
        items, _ = await self.list(
            filters={"target_direction_id": direction_id},
            only_active=True,
            order_by="sort_order",
            limit=200,
        )
        return items

    async def list_auto_assign(self) -> list[RoutingRule]:
        items, _ = await self.list(
            filters={"auto_assign": True},
            only_active=True,
            order_by="sort_order",
            limit=200,
        )
        return items

    async def find_matching_rule(
        self,
        *,
        category: str | None = None,
        priority: str | None = None,
        source: str | None = None,
        title: str = "",
        description: str = "",
    ) -> RoutingRule | None:
        """Évalue les règles actives dans l'ordre (sort_order ASC) et retourne la première qui matche."""
        rules = await self.list_ordered()
        text = f"{title} {description}".lower()
        for rule in rules:
            field = rule.condition_field
            val = rule.condition_value
            if field == "category":
                if category and category.lower() == val.lower():
                    return rule
            elif field == "priority":
                if priority and priority.lower() == val.lower():
                    return rule
            elif field == "source":
                if source and source.lower() == val.lower():
                    return rule
            elif field == "keyword":
                keywords = [k.strip().lower() for k in val.split(",") if k.strip()]
                if any(kw in text for kw in keywords):
                    return rule
        return None
