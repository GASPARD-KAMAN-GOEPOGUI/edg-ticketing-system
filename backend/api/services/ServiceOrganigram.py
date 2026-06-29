from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.RepositoryOrganigram import OrganigramRepository
from api.services.base_service import BaseService


class OrganigramService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = OrganigramRepository(session)

    async def list_all(self, *, page: int = 1, limit: int = 500):
        items, total = await self.repo.list(order_by="id", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_roots(self):
        return await self.repo.list_roots()

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Nœud organigramme introuvable")
        return obj

    async def create(self, data: dict):
        return await self.repo.create(data)

    async def update(self, id: str, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Nœud organigramme introuvable")
        return obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def get_children(self, id: str) -> dict:
        await self.get_by_id(id)
        children = await self.repo.list_children(int(id))
        return {"organigram_id": id, "children": children}

    async def get_ancestors(self, id: str) -> dict:
        await self.get_by_id(id)
        rows = await self.repo.get_ancestors(int(id))
        return {"organigram_id": id, "ancestors": rows}

    async def get_descendants(self, id: str) -> dict:
        await self.get_by_id(id)
        rows = await self.repo.get_descendants(int(id))
        return {"organigram_id": id, "descendants": rows}

    async def get_tree(self, id: str) -> dict:
        await self.get_by_id(id)
        return await self.repo.get_tree_json(int(id))
