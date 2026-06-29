from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import CommunicationSettingRepository
from api.services.base_service import BaseService


class CommunicationSettingService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = CommunicationSettingRepository(session)

    async def get_current(self):
        obj = await self.repo.get_current()
        if obj is None:
            raise self.not_found("Paramètres de communication non configurés")
        return obj

    async def get_or_create_default(self):
        return await self.repo.get_or_create_default()

    async def update_current(self, data: dict, *, updated_by: str | None = None):
        obj = await self.repo.update_current(data, updated_by=updated_by)
        if obj is None:
            obj = await self.repo.get_or_create_default()
            obj = await self.repo.update_current(data, updated_by=updated_by)
        return obj
