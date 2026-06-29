from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ModelAnnouncementStatus import AnnouncementStatus
from api.repositories.base_repository import ReferenceBaseRepository


class AnnouncementStatusRepository(ReferenceBaseRepository[AnnouncementStatus]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnnouncementStatus, session)
