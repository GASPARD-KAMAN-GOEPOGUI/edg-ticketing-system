from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.RepositoryUnity import UnityRepository
from api.services.base_service import BaseService


class UnityService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = UnityRepository(session)

    async def list_all(self, *, page: int = 1, limit: int = 200):
        items, total = await self.repo.list(order_by="label", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_active(self):
        items, _ = await self.repo.list_active()
        return items

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Unity introuvable")
        return obj

    async def get_by_codename(self, codename: str):
        obj = await self.repo.find_by_codename(codename)
        if obj is None:
            raise self.not_found(f"Codename '{codename}' introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_codename(data.get("codename", ""))
        if existing:
            raise self.conflict("Une unity avec ce codename existe déjà")
        return await self.repo.create(data)

    async def update(self, id: str, data: dict):
        if "codename" in data and data["codename"]:
            existing = await self.repo.find_by_codename(data["codename"])
            if existing and str(existing.id) != str(id):
                raise self.conflict("Ce codename est déjà utilisé")
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Unity introuvable")
        return obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def search(self, q: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.search(q, page=page, limit=limit)
        return self.paginate(items, total, page, limit)
