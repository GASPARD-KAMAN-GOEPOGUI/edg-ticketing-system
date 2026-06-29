from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ModelAnnouncementCategory import AnnouncementCategory
from api.repositories.base_repository import ReferenceBaseRepository


class AnnouncementCategoryRepository(ReferenceBaseRepository[AnnouncementCategory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnnouncementCategory, session)
