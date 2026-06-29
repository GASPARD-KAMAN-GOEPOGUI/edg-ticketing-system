from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelAnnouncementTargetRole import AnnouncementTargetRole
from api.repositories.base_repository import BaseRepository


class AnnouncementTargetRoleRepository(BaseRepository[AnnouncementTargetRole]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnnouncementTargetRole, session)

    async def list_by_announcement(
        self, announcement_id: str
    ) -> list[AnnouncementTargetRole]:
        items, _ = await self.list(
            filters={"announcement_id": announcement_id},
            limit=20,
        )
        return items

    async def list_by_role(
        self, role: str, *, page: int = 1, limit: int = 50
    ) -> tuple[list[AnnouncementTargetRole], int]:
        return await self.list(
            filters={"role": role},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def bulk_set_roles(
        self, announcement_id: str, roles: list[str]
    ) -> list[AnnouncementTargetRole]:
        """Remplace tous les rôles cibles d'une annonce par la nouvelle liste."""
        existing = await self.list_by_announcement(announcement_id)
        for obj in existing:
            await self.hard_delete(obj.id)
        return await self.bulk_create(
            [{"announcement_id": announcement_id, "role": r} for r in roles]
        )
