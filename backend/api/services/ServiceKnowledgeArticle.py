from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import KnowledgeArticleRepository
from api.services.base_service import BaseService


class KnowledgeArticleService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = KnowledgeArticleRepository(session)

    async def list_published(self, *, category: str | None = None, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_published(category=category, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_category(self, category: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_category(category, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(order_by="-created_at", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Article introuvable")
        return obj

    async def create(self, data: dict):
        return await self.repo.create(data)

    async def update(self, id: str, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Article introuvable")
        return obj

    async def publish(self, id: str):
        obj = await self.repo.publish(id)
        if obj is None:
            raise self.not_found("Article introuvable")
        return obj

    async def archive(self, id: str):
        obj = await self.repo.archive(id)
        if obj is None:
            raise self.not_found("Article introuvable")
        return obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def search(self, q: str, *, published_only: bool = True, page: int = 1, limit: int = 20):
        items, total = await self.repo.search(q, published_only=published_only, page=page, limit=limit)
        return self.paginate(items, total, page, limit)
