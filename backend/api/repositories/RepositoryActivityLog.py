from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelActivityLog import ActivityLog
from api.repositories.base_repository import BaseRepository


class ActivityLogRepository(BaseRepository[ActivityLog]):
    """
    Append-only — update() et delete() sont intentionnellement
    désactivés pour préserver l'intégrité de l'audit trail.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ActivityLog, session)

    async def append(self, data: dict) -> ActivityLog:
        """Alias sémantique de create() — rappelle le caractère append-only."""
        return await self.create(data)

    async def list_by_actor(
        self,
        actor_id: str,
        *,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[ActivityLog], int]:
        return await self.list(
            filters={"actor_id": actor_id},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_category(
        self,
        category: str,
        *,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[ActivityLog], int]:
        return await self.list(
            filters={"category": category},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_action(
        self,
        action: str,
        *,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[ActivityLog], int]:
        return await self.list(
            filters={"action": action},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_errors(
        self, *, page: int = 1, limit: int = 50
    ) -> tuple[list[ActivityLog], int]:
        return await self.list(
            filters={"log_status": "error"},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def search(
        self, term: str, *, page: int = 1, limit: int = 50
    ) -> tuple[list[ActivityLog], int]:
        return await self.list(
            search=(["actor", "action", "target", "ip_address"], term),
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    # ── Opérations interdites sur un log d'audit ──────────────────────────────

    async def update(self, id: str, data: dict):  # type: ignore[override]
        raise NotImplementedError("ActivityLog est append-only — update interdit.")

    async def delete(self, id: str) -> bool:  # type: ignore[override]
        raise NotImplementedError("ActivityLog est append-only — soft-delete interdit.")

    async def hard_delete(self, id: str) -> bool:  # type: ignore[override]
        raise NotImplementedError("ActivityLog est append-only — hard-delete interdit.")
