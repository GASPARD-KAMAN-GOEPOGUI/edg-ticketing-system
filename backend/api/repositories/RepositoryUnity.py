from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelUnity import Unity
from api.repositories.base_repository import BaseRepository


class UnityRepository(BaseRepository[Unity]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Unity, session)

    async def find_by_codename(self, codename: str) -> Unity | None:
        return await self.get_one({"codename": codename})

    async def list_active(self, *, page: int = 1, limit: int = 200) -> tuple[list[Unity], int]:
        return await self.list(only_active=True, order_by="label", page=page, limit=limit)

    async def search(self, term: str, *, page: int = 1, limit: int = 20) -> tuple[list[Unity], int]:
        return await self.list(
            search=(["codename", "label", "aleas"], term),
            only_active=True,
            page=page,
            limit=limit,
        )
