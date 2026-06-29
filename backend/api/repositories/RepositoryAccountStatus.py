from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.ModelAccountStatus import AccountStatus
from api.repositories.base_repository import ReferenceBaseRepository


class AccountStatusRepository(ReferenceBaseRepository[AccountStatus]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AccountStatus, session)
