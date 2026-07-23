from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.rbac import normalize_role
from api.models.ModelNotification import Notification
from api.repositories.base_repository import BaseRepository

_ADMIN_ROLES: frozenset[str] = frozenset({"admin"})


def _is_admin_role(actor_role: str) -> bool:
    return normalize_role(actor_role) in _ADMIN_ROLES


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Notification, session)

    async def list_mine(
        self,
        recipient_id: str,
        *,
        actor_role: str = "user",
        unread_only: bool = False,
        nature: str | None = None,
        page: int = 1,
        limit: int = 30,
    ) -> tuple[list[Notification], int]:
        """Liste les notifications d'un destinataire avec filtres read/nature/visibility."""
        base = [
            Notification.recipient_id == recipient_id,
            Notification.deleted_at.is_(None),
        ]
        if not _is_admin_role(actor_role):
            base.append(Notification.visibility == "public")
        if unread_only:
            base.append(Notification.is_read == False)  # noqa: E712
        if nature == "annonce":
            base.append(Notification.request_id.is_(None))
        elif nature == "demande":
            base.append(Notification.request_id.isnot(None))

        cnt_stmt = select(func.count()).select_from(Notification)
        for c in base:
            cnt_stmt = cnt_stmt.where(c)
        total = (await self.session.execute(cnt_stmt)).scalar_one() or 0

        data_stmt = select(Notification)
        for c in base:
            data_stmt = data_stmt.where(c)
        data_stmt = (
            data_stmt.order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(max(0, (page - 1) * limit))
        )
        rows = await self.session.execute(data_stmt)
        return list(rows.scalars().all()), total

    async def list_by_recipient(
        self,
        recipient_id: str,
        *,
        actor_role: str = "user",
        unread_only: bool = False,
        page: int = 1,
        limit: int = 30,
    ) -> tuple[list[Notification], int]:
        filters: dict = {"recipient_id": recipient_id}
        if unread_only:
            filters["is_read"] = False
        if not _is_admin_role(actor_role):
            filters["visibility"] = "public"
        return await self.list(
            filters=filters,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def count_unread(self, recipient_id: str, *, actor_role: str = "user") -> int:
        conds = [
            Notification.recipient_id == recipient_id,
            Notification.is_read == False,  # noqa: E712
            Notification.deleted_at.is_(None),
        ]
        if not _is_admin_role(actor_role):
            conds.append(Notification.visibility == "public")
        stmt = select(func.count()).select_from(Notification)
        for c in conds:
            stmt = stmt.where(c)
        return (await self.session.execute(stmt)).scalar_one() or 0

    async def mark_as_read(self, id: str) -> Notification | None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return await self.update(id, {"is_read": True, "read_at": now})

    async def mark_all_read(self, recipient_id: str) -> int:
        """Marque toutes les notifications d'un destinataire comme lues.
        Retourne le nombre de lignes affectées."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            update(Notification)
            .where(Notification.recipient_id == recipient_id)
            .where(Notification.is_read == False)  # noqa: E712
            .where(Notification.deleted_at.is_(None))
            .values(is_read=True, read_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def list_by_request(
        self, request_id: str, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Notification], int]:
        return await self.list(
            filters={"request_id": request_id},
            order_by="-created_at",
            page=page,
            limit=limit,
        )
