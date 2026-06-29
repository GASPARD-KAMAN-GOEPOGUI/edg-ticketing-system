from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ModelRequestStatus import RequestStatus
from api.repositories.base_repository import ReferenceBaseRepository


class RequestStatusRepository(ReferenceBaseRepository[RequestStatus]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RequestStatus, session)
