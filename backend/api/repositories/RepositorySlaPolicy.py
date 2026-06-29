from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelSlaPolicy import SlaPolicy
from api.repositories.base_repository import BaseRepository


class SlaPolicyRepository(BaseRepository[SlaPolicy]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SlaPolicy, session)

    async def find_policy(
        self, category: str, priority: str
    ) -> SlaPolicy | None:
        """Retourne la politique SLA pour une combinaison catégorie/priorité."""
        return await self.get_one({"category": category, "priority": priority})

    async def list_by_category(
        self, category: str
    ) -> list[SlaPolicy]:
        items, _ = await self.list(
            filters={"category": category},
            only_active=True,
            limit=100,
        )
        return items

    async def list_all_active(self) -> list[SlaPolicy]:
        items, _ = await self.list(only_active=True, limit=500)
        return items
