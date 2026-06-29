from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelCommunicationSetting import CommunicationSetting
from api.repositories.base_repository import BaseRepository


class CommunicationSettingRepository(BaseRepository[CommunicationSetting]):
    """
    Singleton fonctionnel — une seule ligne en production.
    get_current() retourne toujours la config active la plus récente.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CommunicationSetting, session)

    async def get_current(self) -> CommunicationSetting | None:
        """Retourne la configuration de communication active (singleton)."""
        items, _ = await self.list(
            only_active=True,
            order_by="-created_at",
            limit=1,
        )
        return items[0] if items else None

    async def get_or_create_default(self) -> CommunicationSetting:
        """Retourne la config existante ou crée les valeurs par défaut."""
        obj = await self.get_current()
        if obj:
            return obj
        return await self.create({})

    async def update_current(
        self, data: dict, updated_by: str | None = None
    ) -> CommunicationSetting | None:
        """Met à jour la configuration active."""
        obj = await self.get_current()
        if obj is None:
            return None
        if updated_by:
            data["updated_by"] = updated_by
        return await self.update(obj.id, data)
