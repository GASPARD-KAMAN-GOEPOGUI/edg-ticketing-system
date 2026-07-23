from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.rbac import normalize_role
from api.models.ModelAnnouncement import Announcement
from api.models.ModelAnnouncementCategory import AnnouncementCategory
from api.models.ModelAnnouncementPriority import AnnouncementPriority
from api.models.ModelAnnouncementStatus import AnnouncementStatus
from api.repositories.base_repository import BaseRepository

_ADMIN_ROLES: frozenset[str] = frozenset({"admin"})


def _is_admin_role(actor_role: str) -> bool:
    return normalize_role(actor_role) in _ADMIN_ROLES


class AnnouncementRepository(BaseRepository[Announcement]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Announcement, session)

    # ── Surcharge _apply_filters : traduit code → subquery FK ─────────────────

    _CODE_FK_MAP: dict = {
        "announcement_status": (
            Announcement.announcement_status_id, AnnouncementStatus, "code"
        ),
        "announcement_priority": (
            Announcement.announcement_priority_id, AnnouncementPriority, "code"
        ),
        "announcement_category": (
            Announcement.announcement_category_id, AnnouncementCategory, "code"
        ),
    }

    def _apply_filters(self, stmt, filters: dict):
        regular: dict = {}
        for key, val in filters.items():
            if key in self._CODE_FK_MAP:
                fk_col, ref_model, code_attr = self._CODE_FK_MAP[key]
                ref_col = getattr(ref_model, code_attr)
                sub = select(ref_model.id).where(ref_model.deleted_at.is_(None))
                if isinstance(val, (list, tuple, set)):
                    sub = sub.where(ref_col.in_(list(val)))
                    stmt = stmt.where(fk_col.in_(sub))
                else:
                    stmt = stmt.where(
                        fk_col == sub.where(ref_col == val).scalar_subquery()
                    )
            else:
                regular[key] = val
        return super()._apply_filters(stmt, regular)

    # ── Helpers de subquery internes ──────────────────────────────────────────

    def _status_sub(self, code: str):
        return (
            select(AnnouncementStatus.id)
            .where(AnnouncementStatus.code == code)
            .where(AnnouncementStatus.deleted_at.is_(None))
            .scalar_subquery()
        )

    def _priority_in_sub(self, codes: list[str]):
        return (
            select(AnnouncementPriority.id)
            .where(AnnouncementPriority.code.in_(codes))
            .where(AnnouncementPriority.deleted_at.is_(None))
        )

    # ── Méthodes de liste ─────────────────────────────────────────────────────

    async def list_published(
        self,
        *,
        actor_role: str = "user",
        audience: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Announcement], int]:
        filters: dict = {"announcement_status": "published"}
        if audience:
            filters["audience"] = audience
        if not _is_admin_role(actor_role):
            filters["visibility"] = "public"
        return await self.list(
            filters=filters,
            only_active=True,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_status(
        self,
        status: str,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Announcement], int]:
        return await self.list(
            filters={"announcement_status": status},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_author(
        self,
        author_id: str,
        *,
        actor_role: str = "user",
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Announcement], int]:
        filters: dict = {"author_id": author_id}
        if not _is_admin_role(actor_role):
            filters["visibility"] = "public"
        return await self.list(
            filters=filters,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_active_for_audience(
        self, audience: str, *, actor_role: str = "user", page: int = 1, limit: int = 20
    ) -> tuple[list[Announcement], int]:
        """Annonces publiées non expirées pour une audience donnée."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        published_sub = self._status_sub("published")
        stmt = (
            select(Announcement)
            .where(Announcement.announcement_status_id == published_sub)
            .where(Announcement.audience.in_([audience, "all"]))
            .where(Announcement.deleted_at.is_(None))
            .where(
                (Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)
            )
            .order_by(Announcement.created_at.desc())
        )
        count_stmt = (
            select(func.count())
            .select_from(Announcement)
            .where(Announcement.announcement_status_id == published_sub)
            .where(Announcement.audience.in_([audience, "all"]))
            .where(Announcement.deleted_at.is_(None))
            .where(
                (Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)
            )
        )
        if not _is_admin_role(actor_role):
            stmt = stmt.where(Announcement.visibility == "public")
            count_stmt = count_stmt.where(Announcement.visibility == "public")
        total = (await self.session.execute(count_stmt)).scalar_one() or 0
        stmt = stmt.limit(limit).offset(max(0, (page - 1) * limit))
        rows = await self.session.execute(stmt)
        return list(rows.scalars().all()), total

    async def list_active_alerts(
        self, *, actor_role: str = "user", page: int = 1, limit: int = 100
    ) -> tuple[list[Announcement], int]:
        """Annonces publiées critiques/absolute_emergency non expirées."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        published_sub = self._status_sub("published")
        priority_sub = self._priority_in_sub(["critical", "absolute_emergency"])
        stmt = (
            select(Announcement)
            .where(Announcement.announcement_status_id == published_sub)
            .where(Announcement.announcement_priority_id.in_(priority_sub))
            .where(Announcement.deleted_at.is_(None))
            .where(
                (Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)
            )
            .order_by(Announcement.created_at.desc())
        )
        count_stmt = (
            select(func.count())
            .select_from(Announcement)
            .where(Announcement.announcement_status_id == published_sub)
            .where(Announcement.announcement_priority_id.in_(priority_sub))
            .where(Announcement.deleted_at.is_(None))
            .where(
                (Announcement.expires_at.is_(None)) | (Announcement.expires_at > now)
            )
        )
        if not _is_admin_role(actor_role):
            stmt = stmt.where(Announcement.visibility == "public")
            count_stmt = count_stmt.where(Announcement.visibility == "public")
        total = (await self.session.execute(count_stmt)).scalar_one() or 0
        stmt = stmt.limit(limit).offset(max(0, (page - 1) * limit))
        rows = await self.session.execute(stmt)
        return list(rows.scalars().all()), total

    async def publish(self, id: str) -> Announcement | None:
        result = await self.session.execute(
            select(AnnouncementStatus.id)
            .where(AnnouncementStatus.code == "published")
            .where(AnnouncementStatus.deleted_at.is_(None))
        )
        status_id = result.scalar_one_or_none()
        if status_id is None:
            return None
        return await self.update(id, {"announcement_status_id": status_id})

    async def close(self, id: str) -> Announcement | None:
        result = await self.session.execute(
            select(AnnouncementStatus.id)
            .where(AnnouncementStatus.code == "closed")
            .where(AnnouncementStatus.deleted_at.is_(None))
        )
        status_id = result.scalar_one_or_none()
        if status_id is None:
            return None
        closed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        return await self.update(id, {"announcement_status_id": status_id, "closed_at": closed_at})

    async def search(
        self, term: str, *, actor_role: str = "user", page: int = 1, limit: int = 20
    ) -> tuple[list[Announcement], int]:
        filters: dict = {}
        if not _is_admin_role(actor_role):
            filters["visibility"] = "public"
        return await self.list(
            search=(["title", "description"], term),
            filters=filters if filters else None,
            order_by="-created_at",
            page=page,
            limit=limit,
        )
