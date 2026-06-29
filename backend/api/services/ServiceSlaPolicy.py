from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import SlaPolicyRepository
from api.services.base_service import BaseService


class SlaPolicyService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = SlaPolicyRepository(session)

    async def list_all(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list(order_by="-created_at", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_category(self, category_id: str):
        return await self.repo.list_by_category(category_id)

    async def list_active(self):
        return await self.repo.list_all_active()

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Politique SLA introuvable")
        return obj

    async def find_policy(self, category: str, priority: str):
        obj = await self.repo.find_policy(category, priority)
        if obj is None:
            raise self.not_found(
                f"Aucune politique SLA pour catégorie='{category}' priorité='{priority}'"
            )
        return obj

    async def create(self, data: dict):
        return await self.repo.create(data)

    async def update(self, id: str, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Politique SLA introuvable")
        return obj

    async def toggle(self, id: str):
        obj = await self.get_by_id(id)
        updated = await self.repo.update(id, {"status": not obj.status})
        return updated

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)
