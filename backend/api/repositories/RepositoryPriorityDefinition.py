from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelPriorityDefinition import PriorityDefinition
from api.repositories.base_repository import BaseRepository


class PriorityDefinitionRepository(BaseRepository[PriorityDefinition]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(PriorityDefinition, session)

    async def find_by_slug(self, slug: str) -> PriorityDefinition | None:
        return await self.get_one({"slug": slug})

    async def list_ordered(self, *, only_active: bool | None = True) -> list[PriorityDefinition]:
        items, _ = await self.list(
            order_by="sort_order",
            limit=100,
            only_active=only_active,
        )
        return items

    async def list_builtin(self) -> list[PriorityDefinition]:
        items, _ = await self.list(
            filters={"is_builtin": True},
            order_by="sort_order",
            limit=100,
        )
        return items
