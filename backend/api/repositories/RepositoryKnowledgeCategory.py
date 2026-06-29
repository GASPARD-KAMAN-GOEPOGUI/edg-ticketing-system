from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ModelKnowledgeCategory import KnowledgeCategory
from api.repositories.base_repository import ReferenceBaseRepository


class KnowledgeCategoryRepository(ReferenceBaseRepository[KnowledgeCategory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(KnowledgeCategory, session)
