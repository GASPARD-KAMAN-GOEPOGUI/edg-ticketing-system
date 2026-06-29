from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelSecurityIncident import SecurityIncident
from api.repositories.base_repository import BaseRepository

_DEDUP_WINDOW_MINUTES = 15


class SecurityIncidentRepository(BaseRepository[SecurityIncident]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SecurityIncident, session)

    async def list_all(self, *, page: int = 1, limit: int = 50) -> tuple[list[SecurityIncident], int]:
        return await self.list(
            include_deleted=True,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_unresolved(self) -> list[SecurityIncident]:
        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .where(self.model.resolved.is_(False))
            .order_by(self.model.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_recent_by_identifier(self, identifier: str) -> SecurityIncident | None:
        """
        Retourne l'incident non résolu le plus récent pour cet identifiant,
        créé dans la fenêtre de déduplication (15 min).
        """
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=_DEDUP_WINDOW_MINUTES)
        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .where(self.model.resolved.is_(False))
            .where(self.model.email_attempted == identifier)
            .where(self.model.created_at >= cutoff)
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def increment_attempt(self, incident: SecurityIncident, *, new_photo_path: str | None, occurred_at: str, attempt_count: int) -> SecurityIncident:
        """Met à jour attempt_count et la photo sur un incident existant."""
        patch: dict = {"attempt_count": attempt_count}
        if new_photo_path:
            patch["photo_path"] = new_photo_path
        patch["occurred_at"] = occurred_at
        return await self.update(incident.id, patch)

    async def resolve(self, incident_id: int, *, resolver_id: int, notes: str | None) -> SecurityIncident:
        obj = await self.get_by_id(incident_id)
        if obj is None:
            raise ValueError("Incident introuvable")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return await self.update(incident_id, {
            "resolved": True,
            "resolved_at": now,
            "resolved_by": resolver_id,
            "notes": notes,
        })
