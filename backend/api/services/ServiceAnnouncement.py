from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelAnnouncementCategory import AnnouncementCategory
from api.models.ModelAnnouncementPriority import AnnouncementPriority
from api.models.ModelAnnouncementStatus import AnnouncementStatus
from api.core.rbac import normalize_role
from api.repositories import (
    AnnouncementRepository,
    AnnouncementTargetRoleRepository,
)
from api.core.event_bus import AppEvent, emit as emit_event
from api.services.base_service import BaseService
from api.services.NotificationEmitter import emit_bulk as emit_notif_bulk

_ADMIN_ROLES: frozenset[str] = frozenset({"admin"})


def _is_admin_role(actor_role: str) -> bool:
    return normalize_role(actor_role) in _ADMIN_ROLES


def _normalize_target_roles(roles: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for role in roles:
        value = normalize_role(role)
        if value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


class AnnouncementService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AnnouncementRepository(session)
        self.role_repo = AnnouncementTargetRoleRepository(session)

    # ── Helper : traduit codes string → IDs FK ────────────────────────────────

    async def _translate_codes(self, data: dict) -> dict:
        out = dict(data)
        if "announcement_category" in out:
            code = out.pop("announcement_category")
            r = await self.session.execute(
                select(AnnouncementCategory.id)
                .where(AnnouncementCategory.code == code)
                .where(AnnouncementCategory.deleted_at.is_(None))
            )
            out["announcement_category_id"] = r.scalar_one()
        if "announcement_priority" in out:
            code = out.pop("announcement_priority")
            r = await self.session.execute(
                select(AnnouncementPriority.id)
                .where(AnnouncementPriority.code == code)
                .where(AnnouncementPriority.deleted_at.is_(None))
            )
            out["announcement_priority_id"] = r.scalar_one()
        if "announcement_status" in out:
            code = out.pop("announcement_status")
            r = await self.session.execute(
                select(AnnouncementStatus.id)
                .where(AnnouncementStatus.code == code)
                .where(AnnouncementStatus.deleted_at.is_(None))
            )
            out["announcement_status_id"] = r.scalar_one()
        return out

    # ── Listes ────────────────────────────────────────────────────────────────

    async def list_all(self, *, actor_role: str = "user", page: int = 1, limit: int = 20):
        filters = None if _is_admin_role(actor_role) else {"visibility": "public"}
        items, total = await self.repo.list(
            filters=filters,
            order_by="-created_at",
            page=page,
            limit=limit,
        )
        return self.paginate(items, total, page, limit)

    async def list_published(self, *, actor_role: str = "user", audience: str | None = None, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_published(actor_role=actor_role, audience=audience, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_active_for_audience(self, audience: str, *, actor_role: str = "user", page: int = 1, limit: int = 20):
        items, total = await self.repo.list_active_for_audience(audience, actor_role=actor_role, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_active_alerts(self, *, actor_role: str = "user", page: int = 1, limit: int = 100):
        items, total = await self.repo.list_active_alerts(actor_role=actor_role, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_author(self, author_id: str, *, actor_role: str = "user", page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_author(author_id, actor_role=actor_role, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Annonce introuvable")
        return obj

    async def create(self, data: dict):
        data.pop("channel_names", None)
        data.pop("unity_ids", None)
        data.pop("direction_ids", None)
        role_names = _normalize_target_roles(data.pop("role_names", []))
        translated = await self._translate_codes(data)
        obj = await self.repo.create(translated)
        if role_names:
            await self.role_repo.bulk_set_roles(obj.id, role_names)
        await emit_event(AppEvent(
            type="announcement.created",
            payload={"id": obj.id},
            target={"roles": "all"},
        ))
        return await self.repo.get_by_id(obj.id)

    async def update(self, id: str, data: dict):
        data.pop("channel_names", None)
        data.pop("unity_ids", None)
        data.pop("direction_ids", None)
        role_names = data.pop("role_names", None)
        if role_names is not None:
            role_names = _normalize_target_roles(role_names)
        if data:
            translated = await self._translate_codes(data)
            obj = await self.repo.update(id, translated)
            if obj is None:
                raise self.not_found("Annonce introuvable")
        else:
            obj = await self.repo.get_by_id(id)
            if obj is None:
                raise self.not_found("Annonce introuvable")
        if role_names is not None:
            await self.role_repo.bulk_set_roles(id, role_names)
        return await self.repo.get_by_id(id)

    async def publish(self, id: str):
        obj = await self.repo.publish(id)
        if obj is None:
            raise self.not_found("Annonce introuvable")

        # Fan-out notification in-app vers les destinataires (CDC §6.7)
        try:
            from sqlalchemy import select as _sel
            from api.models.ModelAccount import Account as _Account

            audience = getattr(obj, "audience", "internal")
            target_unit_id = None
            if isinstance(getattr(obj, "infos", None), dict):
                target_unit_id = obj.infos.get("target_unit_id")

            # Filtre les comptes destinataires selon l'audience
            stmt = _sel(_Account.id).where(
                _Account.account_status == "active",
                _Account.deleted_at.is_(None),
            )
            if audience == "unit" and target_unit_id:
                stmt = stmt.where(_Account.unity_id == int(target_unit_id))
            # audience "all" et "internal" → tous les comptes actifs

            result = await self.session.execute(stmt)
            recipient_ids = [str(row[0]) for row in result.all()]

            if recipient_ids:
                await emit_notif_bulk(
                    self.session,
                    recipient_ids=recipient_ids,
                    title=f"Annonce : {obj.title}",
                    body=obj.description[:120] + ("…" if len(obj.description) > 120 else ""),
                    type="info",
                    action_label="Voir l'annonce",
                    action_url="/app/notifications",
                )
        except Exception as exc:
            self._logger.warning("publish fan-out notifications échoué : %s", exc)

        await emit_event(AppEvent(
            type="announcement.published",
            payload={"id": id},
            target={"roles": "all"},
        ))
        return obj

    async def close(self, id: str):
        obj = await self.repo.close(id)
        if obj is None:
            raise self.not_found("Annonce introuvable")
        await emit_event(AppEvent(
            type="announcement.closed",
            payload={"id": id},
            target={"roles": "all"},
        ))
        return obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def search(self, q: str, *, actor_role: str = "user", page: int = 1, limit: int = 20):
        items, total = await self.repo.search(q, actor_role=actor_role, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    # ── Target roles ──────────────────────────────────────────────────────────

    async def list_target_roles(self, announcement_id: str):
        return await self.role_repo.list_by_announcement(announcement_id)

    async def set_target_roles(self, announcement_id: str, roles: list[str]):
        return await self.role_repo.bulk_set_roles(
            announcement_id,
            _normalize_target_roles(roles),
        )
