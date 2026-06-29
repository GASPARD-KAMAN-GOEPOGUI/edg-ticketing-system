from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelAttachment import Attachment
from api.repositories.base_repository import BaseRepository


class AttachmentRepository(BaseRepository[Attachment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Attachment, session)

    async def list_by_request(
        self, request_id: str, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Attachment], int]:
        return await self.list(
            filters={"request_id": request_id},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_pending_scan(
        self, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Attachment], int]:
        return await self.list(
            filters={"scan_status": "pending_scan"},
            order_by="created_at",
            page=page,
            limit=limit,
        )

    async def list_quarantined(
        self, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Attachment], int]:
        return await self.list(
            filters={"scan_status": "quarantined"},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def update_scan_result(
        self, id: str, *, clamav_clean: bool, scan_status: str
    ) -> Attachment | None:
        return await self.update(id, {"clamav_clean": clamav_clean, "scan_status": scan_status})
