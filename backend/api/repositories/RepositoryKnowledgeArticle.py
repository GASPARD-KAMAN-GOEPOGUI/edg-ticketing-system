from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelKnowledgeArticle import KnowledgeArticle
from api.repositories.base_repository import BaseRepository


class KnowledgeArticleRepository(BaseRepository[KnowledgeArticle]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(KnowledgeArticle, session)

    async def list_published(
        self,
        *,
        category: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[KnowledgeArticle], int]:
        filters: dict = {"is_published": True, "is_archived": False}
        if category:
            filters["category"] = category
        return await self.list(
            filters=filters,
            only_active=True,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_category(
        self, category: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[KnowledgeArticle], int]:
        return await self.list(
            filters={"category": category, "is_archived": False},
            only_active=True,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def search(
        self, term: str, *, published_only: bool = True, page: int = 1, limit: int = 20
    ) -> tuple[list[KnowledgeArticle], int]:
        filters: dict = {"is_archived": False}
        if published_only:
            filters["is_published"] = True
        return await self.list(
            filters=filters,
            search=(["title", "excerpt", "body", "author"], term),
            only_active=True,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def publish(self, id: str) -> KnowledgeArticle | None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return await self.update(id, {"is_published": True, "published_at": now})

    async def archive(self, id: str) -> KnowledgeArticle | None:
        return await self.update(id, {"is_archived": True, "is_published": False})
