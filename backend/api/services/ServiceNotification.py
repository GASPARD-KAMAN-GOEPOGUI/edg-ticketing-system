from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.event_bus import AppEvent, emit as emit_event
from api.repositories import NotificationRepository
from api.services.base_service import BaseService


class NotificationService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = NotificationRepository(session)

    async def list_mine(
        self,
        recipient_id: str,
        *,
        actor_role: str = "user",
        unread_only: bool = False,
        nature: str | None = None,
        archived: bool = False,
        page: int = 1,
        limit: int = 30,
    ):
        """Notifications de l'utilisateur courant — filtrées par visibilité selon le rôle."""
        items, total = await self.repo.list_mine(
            recipient_id,
            actor_role=actor_role,
            unread_only=unread_only,
            nature=nature,
            archived=archived,
            page=page,
            limit=limit,
        )
        return self.paginate(items, total, page, limit)

    async def list_by_recipient(
        self,
        recipient_id: str,
        *,
        actor_role: str = "user",
        unread_only: bool = False,
        page: int = 1,
        limit: int = 20,
    ):
        items, total = await self.repo.list_by_recipient(
            recipient_id,
            actor_role=actor_role,
            unread_only=unread_only,
            page=page,
            limit=limit,
        )
        return self.paginate(items, total, page, limit)

    async def list_by_request(self, request_id: str, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_by_request(request_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def count_unread(self, recipient_id: str, *, actor_role: str = "user") -> int:
        return await self.repo.count_unread(recipient_id, actor_role=actor_role)

    async def get_by_id(self, id: str, *, include_deleted: bool = False):
        obj = await self.repo.get_by_id(id, include_deleted=include_deleted)
        if obj is None:
            raise self.not_found("Notification introuvable")
        return obj

    async def create(self, data: dict):
        obj = await self.repo.create(data)
        recipient_id = data.get("recipient_id")
        if recipient_id:
            await emit_event(AppEvent(
                type="notification.created",
                payload={"id": obj.id, "title": data.get("title", "")},
                target={"user_ids": [int(recipient_id)] if str(recipient_id).isdigit() else []},
            ))
        return obj

    async def mark_as_read(self, id: str):
        obj = await self.repo.mark_as_read(id)
        if obj is None:
            raise self.not_found("Notification introuvable")
        return obj

    async def mark_all_read(self, recipient_id: str) -> int:
        return await self.repo.mark_all_read(recipient_id)

    async def delete(self, id: str) -> bool:
        """Archive la notification — soft-delete uniquement (deleted_at), jamais de suppression physique."""
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def restore(self, id: str):
        """Restaure une notification archivée — visible à nouveau dans la vue active."""
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Notification introuvable")
        return await self.repo.get_by_id(id)
