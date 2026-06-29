from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import AttachmentRepository
from api.services.base_service import BaseService


class AttachmentService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AttachmentRepository(session)

    async def list_by_request(self, request_id: str, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_by_request(request_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_pending_scan(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_pending_scan(page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_quarantined(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_quarantined(page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Pièce jointe introuvable")
        return obj

    async def create(self, data: dict):
        return await self.repo.create(data)

    async def update_scan_result(self, id: str, *, clamav_clean: bool, scan_status: str):
        """
        H-04 — signature corrigée : clamav_clean (bool) + scan_status (str),
        alignée avec RepositoryAttachment.update_scan_result().
        """
        obj = await self.repo.update_scan_result(id, clamav_clean=clamav_clean, scan_status=scan_status)
        if obj is None:
            raise self.not_found("Pièce jointe introuvable")
        return obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)
