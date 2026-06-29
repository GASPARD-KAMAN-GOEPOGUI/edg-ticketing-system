from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelRequestStatus import RequestStatus
from api.repositories import AppreciationRepository, RequestRepository
from api.services.base_service import BaseService


class AppreciationService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AppreciationRepository(session)
        self.request_repo = RequestRepository(session)

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(order_by="-created_at", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_rating(self, rating: int, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_rating(rating, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Appréciation introuvable")
        return obj

    async def get_by_request(self, request_id: str):
        obj = await self.repo.find_by_request(request_id)
        if obj is None:
            raise self.not_found("Aucune appréciation pour cette requête")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_request(data.get("request_id", ""))
        if existing:
            raise self.conflict("Une appréciation existe déjà pour cette requête")
        return await self.repo.create(data)

    async def update(self, id: str, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Appréciation introuvable")
        updated = await self.repo.mark_modified(id)
        return updated if updated is not None else obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def average_rating(self, *, only_confirmed: bool = True) -> float:
        return await self.repo.average_rating(only_confirmed=only_confirmed)

    async def count_by_rating(self) -> dict[int, int]:
        return await self.repo.count_by_rating()

    # ── Nested endpoints /requests/:id/appreciation ───────────────────────────

    async def get_by_request_or_none(self, request_id: str):
        """Retourne l'appréciation ou None (pas de 404)."""
        return await self.repo.find_by_request(request_id)

    async def create_for_request(self, request_id: str, data: dict):
        req = await self.request_repo.get_by_id(request_id)
        if req is None:
            raise self.not_found("Demande introuvable")
        if req.request_status not in ("resolved", "closed"):
            raise self.bad_request(
                "L'appréciation n'est disponible que pour les demandes résolues ou clôturées"
            )
        existing = await self.repo.find_by_request(request_id)
        if existing:
            raise self.conflict("Une appréciation existe déjà pour cette demande")

        data["request_id"] = request_id
        obj = await self.repo.create(data)

        if not data.get("resolved_confirmed", True):
            await self._reopen_request(request_id)

        return obj

    async def _reopen_request(self, request_id: str) -> None:
        r = await self.session.execute(
            select(RequestStatus.id)
            .where(RequestStatus.code == "reopened")
            .where(RequestStatus.deleted_at.is_(None))
        )
        status_id = r.scalar_one()
        await self.request_repo.update(request_id, {"request_status_id": status_id})

    async def update_for_request(self, request_id: str, data: dict):
        existing = await self.repo.find_by_request(request_id)
        if not existing:
            raise self.not_found("Aucune appréciation pour cette demande")

        req = await self.request_repo.get_by_id(request_id)
        if req is None:
            raise self.not_found("Demande introuvable")
        if req.request_status == "closed":
            raise self.bad_request(
                "Impossible de modifier l'appréciation d'une demande clôturée"
            )

        obj = await self.repo.update(existing.id, data)
        await self.repo.mark_modified(existing.id)

        if data.get("resolved_confirmed") is False:
            await self._reopen_request(request_id)

        return obj

    # ── CSAT aggregations ─────────────────────────────────────────────────────

    async def csat_global(self) -> dict:
        return await self.repo.csat_global()

    async def csat_by_agent(self) -> list[dict]:
        return await self.repo.csat_by_agent()

    async def csat_by_direction(self) -> list[dict]:
        return await self.repo.csat_by_direction()

    async def csat_by_category(self) -> list[dict]:
        return await self.repo.csat_by_category()

    async def csat_monthly(self, *, months: int = 12) -> list[dict]:
        return await self.repo.csat_monthly(months=months)
