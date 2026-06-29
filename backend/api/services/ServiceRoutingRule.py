from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import RoutingRuleRepository
from api.services.base_service import BaseService


class RoutingRuleService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = RoutingRuleRepository(session)

    async def list_all(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list(
            only_active=True, order_by="sort_order", page=page, limit=limit
        )
        return self.paginate(items, total, page, limit)

    async def list_by_direction(self, direction_id: str):
        return await self.repo.list_by_direction(direction_id)

    async def list_auto_assign(self):
        return await self.repo.list_auto_assign()

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Règle de routage introuvable")
        return obj

    async def create(self, data: dict):
        return await self.repo.create(data)

    async def update(self, id: str, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Règle de routage introuvable")
        return obj

    async def toggle(self, id: str):
        obj = await self.get_by_id(id)
        updated = await self.repo.update(id, {"status": not obj.status})
        return updated

    async def reorder(self, ordered_ids: list[str]) -> list:
        for i, rule_id in enumerate(ordered_ids, 1):
            await self.repo.update(rule_id, {"sort_order": i})
        return await self.repo.list_ordered()

    async def apply_test(self, request_data: dict) -> dict:
        rules = await self.repo.list_ordered()
        for rule in rules:
            if not rule.status:
                continue
            field = rule.condition_field
            value = str(request_data.get(field, ""))
            if field == "keyword":
                keywords = [k.strip().lower() for k in rule.condition_value.split(",")]
                matched = any(k in value.lower() for k in keywords if k)
            else:
                matched = value.lower() == rule.condition_value.lower()
            if matched:
                return {
                    "matched": True,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "target_unity_id": rule.target_unity_id,
                    "auto_assign": rule.auto_assign,
                }
        return {"matched": False}

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)
