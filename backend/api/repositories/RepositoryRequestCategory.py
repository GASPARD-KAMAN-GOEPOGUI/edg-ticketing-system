from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ModelRequestCategory import RequestCategory
from api.repositories.base_repository import ReferenceBaseRepository


class RequestCategoryRepository(ReferenceBaseRepository[RequestCategory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RequestCategory, session)
