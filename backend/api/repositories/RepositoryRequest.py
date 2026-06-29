from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.repositories.base_repository import BaseRepository


class RequestRepository(BaseRepository[Request]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Request, session)

    # ── Statuts par code ──────────────────────────────────────────────────────

    _INACTIVE_STATUSES: list[str] = ["resolved", "closed", "cancelled"]
    _ACTIVE_STATUSES: list[str] = [
        "new", "qualifying", "qualified", "assigned",
        "in_progress", "pending", "escalated", "reopened",
    ]

    # ── Surcharge _apply_filters : traduit code → subquery FK ─────────────────

    _CODE_FK_MAP: dict = {
        "request_status": (
            Request.request_status_id, RequestStatus, "code"
        ),
        "category": (
            Request.request_category_id, RequestCategory, "code"
        ),
        "priority": (
            Request.priority_definition_id, PriorityDefinition, "slug"
        ),
    }

    def _apply_filters(self, stmt, filters: dict):
        filters = dict(filters)
        # Filtres plage de dates sur created_at
        date_from = filters.pop("date_from", None)
        date_to = filters.pop("date_to", None)
        if date_from:
            stmt = stmt.where(Request.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Request.created_at <= date_to)

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

    # ── Helpers subquery internes ──────────────────────────────────────────────

    def _status_in_sub(self, codes: list[str]):
        return (
            select(RequestStatus.id)
            .where(RequestStatus.code.in_(codes))
            .where(RequestStatus.deleted_at.is_(None))
        )

    def _category_sub(self, code: str):
        return (
            select(RequestCategory.id)
            .where(RequestCategory.code == code)
            .where(RequestCategory.deleted_at.is_(None))
            .scalar_subquery()
        )

    # ── Méthodes de recherche / liste ─────────────────────────────────────────

    async def find_by_ref(self, ref: str) -> Request | None:
        return await self.get_one({"ref": ref})

    async def find_duplicate(
        self,
        *,
        title: str,
        category: str,
        requester_id: int | None,
        requester_email: str | None,
        meter_number: str | None,
    ) -> Request | None:
        """Retourne une demande active avec même titre + catégorie + demandeur."""
        title_clean = title.strip().lower()
        if not title_clean or not category:
            return None
        if requester_id is None and not requester_email and not meter_number:
            return None

        inactive_sub = self._status_in_sub(self._INACTIVE_STATUSES)
        cat_sub = self._category_sub(category)

        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .where(func.lower(self.model.title) == title_clean)
            .where(self.model.request_category_id == cat_sub)
            .where(self.model.request_status_id.notin_(inactive_sub))
        )

        if requester_id is not None:
            stmt = stmt.where(self.model.requester_id == requester_id)
        elif requester_email:
            stmt = stmt.where(
                func.lower(self.model.requester_email) == requester_email.strip().lower()
            )
        else:
            stmt = stmt.where(self.model.meter_number == meter_number.strip())

        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_status(
        self, status_code: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"request_status": status_code},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_assignee(
        self,
        assignee_id: str,
        *,
        status_code: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Request], int]:
        filters: dict = {"assignee_id": assignee_id}
        if status_code:
            filters["request_status"] = status_code
        return await self.list(filters=filters, order_by="-created_at", page=page, limit=limit)

    async def list_by_direction(
        self, direction_id: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"unity_id": direction_id},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_pending_triage(
        self, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"in_triage": True},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_sla_breached(
        self, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"sla_breached": True},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_requester(
        self, requester_id: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"requester_id": requester_id},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def search(
        self,
        term: str,
        *,
        filters: dict | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters=filters,
            search=(["ref", "title", "requester_name", "requester_email", "meter_number"], term),
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_queue(
        self,
        *,
        direction_id: str | None = None,
        assignee_id: str | None = None,
        priority: str | None = None,
        request_status: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Request], int]:
        # Si un statut précis est demandé, on filtre sur ce seul statut ;
        # sinon on utilise la liste des statuts actifs par défaut.
        filters: dict = {
            "request_status": request_status if request_status else self._ACTIVE_STATUSES
        }
        if direction_id:
            # Expansion hiérarchique : direction + tous ses services via l'organigramme
            from sqlalchemy import select as _sel
            from api.models.ModelOrganigram import Organigram as _Org
            _r1 = await self.session.execute(
                _sel(_Org.id)
                .where(_Org.unity_id == int(direction_id), _Org.deleted_at.is_(None))
                .limit(1)
            )
            _org_id = _r1.scalar_one_or_none()
            _ids: list[int] = [int(direction_id)]
            if _org_id:
                _r2 = await self.session.execute(
                    _sel(_Org.unity_id)
                    .where(_Org.parent_id == _org_id, _Org.deleted_at.is_(None))
                )
                _ids.extend(uid for (uid,) in _r2.all())
            filters["unity_id"] = _ids
        if assignee_id:
            filters["assignee_id"] = assignee_id
        if priority:
            filters["priority"] = priority
        if search:
            return await self.search(search, filters=filters, page=page, limit=limit)
        return await self.list(filters=filters, order_by="-created_at", page=page, limit=limit)

    async def count_by_status(self) -> dict[str, int]:
        """Retourne {status_code: count} pour le tableau de bord."""
        stmt = (
            select(RequestStatus.code, func.count(Request.id))
            .join(RequestStatus, Request.request_status_id == RequestStatus.id)
            .where(Request.deleted_at.is_(None))
            .group_by(RequestStatus.code)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    async def next_ref(self, year: int) -> str:
        """Calcule la prochaine référence EDG-{year}-{seq:04d}."""
        prefix = f"EDG-{year}-"
        stmt = (
            select(func.count(Request.id))
            .where(Request.ref.like(f"{prefix}%"))
            .where(Request.deleted_at.is_(None))
        )
        count = (await self.session.execute(stmt)).scalar_one() or 0
        return f"{prefix}{count + 1:04d}"
