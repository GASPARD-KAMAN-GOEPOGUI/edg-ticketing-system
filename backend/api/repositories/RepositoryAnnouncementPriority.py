from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ModelAnnouncementPriority import AnnouncementPriority
from api.repositories.base_repository import ReferenceBaseRepository


class AnnouncementPriorityRepository(ReferenceBaseRepository[AnnouncementPriority]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnnouncementPriority, session)
