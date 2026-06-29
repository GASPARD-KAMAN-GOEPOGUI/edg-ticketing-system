from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import ActivityLogRepository
from api.services.base_service import BaseService


class ActivityLogService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = ActivityLogRepository(session)

    async def list_all(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list(order_by="-created_at", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_actor(self, actor_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_actor(actor_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_category(self, category: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_category(category, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_action(self, action: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_action(action, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_errors(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_errors(page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Log d'activité introuvable")
        return obj

    async def append(self, data: dict):
        return await self.repo.append(data)

    async def search(self, q: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.search(q, page=page, limit=limit)
        return self.paginate(items, total, page, limit)
