from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case as sa_case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelAppreciation import Appreciation
from api.repositories.base_repository import BaseRepository


class AppreciationRepository(BaseRepository[Appreciation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Appreciation, session)

    async def find_by_request(self, request_id: str) -> Appreciation | None:
        """Une seule appréciation par requête (contrainte unique)."""
        return await self.get_one({"request_id": request_id})

    async def list_by_rating(
        self,
        rating: int,
        *,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Appreciation], int]:
        return await self.list(
            filters={"rating": rating},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def average_rating(
        self, *, only_confirmed: bool = True
    ) -> float:
        """Calcule la note moyenne globale."""
        stmt = select(func.avg(Appreciation.rating)).where(
            Appreciation.deleted_at.is_(None)
        )
        if only_confirmed:
            stmt = stmt.where(Appreciation.resolved_confirmed == True)  # noqa: E712
        result = await self.session.execute(stmt)
        val = result.scalar_one()
        return float(val) if val is not None else 0.0

    async def count_by_rating(self) -> dict[int, int]:
        """Retourne {1: n, 2: n, ..., 5: n} — distribution des notes."""
        stmt = (
            select(Appreciation.rating, func.count(Appreciation.id))
            .where(Appreciation.deleted_at.is_(None))
            .group_by(Appreciation.rating)
            .order_by(Appreciation.rating)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    async def mark_modified(self, id: str) -> Appreciation | None:
        return await self.update(id, {"is_modified": True})

    async def csat_global(self) -> dict:
        """Stats CSAT globales : moyenne, count, segmentation interne/externe, distribution."""
        agg_stmt = select(
            func.avg(Appreciation.rating).label("avg_all"),
            func.count(Appreciation.id).label("cnt"),
            func.avg(
                sa_case((Appreciation.author_type == "internal", Appreciation.rating), else_=None)
            ).label("avg_internal"),
            func.avg(
                sa_case((Appreciation.author_type == "external", Appreciation.rating), else_=None)
            ).label("avg_external"),
        ).where(Appreciation.deleted_at.is_(None))
        agg = (await self.session.execute(agg_stmt)).one()

        dist_stmt = (
            select(Appreciation.rating, func.count(Appreciation.id).label("n"))
            .where(Appreciation.deleted_at.is_(None))
            .group_by(Appreciation.rating)
            .order_by(Appreciation.rating)
        )
        dist_rows = (await self.session.execute(dist_stmt)).all()

        return {
            "global": round(float(agg.avg_all or 0), 2),
            "count": agg.cnt or 0,
            "internal": round(float(agg.avg_internal or 0), 2),
            "external": round(float(agg.avg_external or 0), 2),
            "distribution": {str(r[0]): r[1] for r in dist_rows},
        }

    async def csat_by_agent(self) -> list[dict]:
        """Moyenne CSAT par agent assigné."""
        from api.models.ModelRequest import Request as Req

        stmt = (
            select(
                Req.assignee_id,
                func.avg(Appreciation.rating).label("avg_rating"),
                func.count(Appreciation.id).label("cnt"),
                func.sum(sa_case((Appreciation.author_type == "internal", 1), else_=0)).label("int_c"),
                func.sum(sa_case((Appreciation.author_type == "external", 1), else_=0)).label("ext_c"),
            )
            .join(Req, Req.id == Appreciation.request_id)
            .where(Appreciation.deleted_at.is_(None))
            .where(Req.deleted_at.is_(None))
            .where(Req.assignee_id.isnot(None))
            .group_by(Req.assignee_id)
            .order_by(func.avg(Appreciation.rating).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "entity_id": r.assignee_id,
                "label": r.assignee_id,
                "avg": round(float(r.avg_rating or 0), 2),
                "count": r.cnt or 0,
                "internal": r.int_c or 0,
                "external": r.ext_c or 0,
            }
            for r in rows
        ]

    async def csat_by_direction(self) -> list[dict]:
        """Moyenne CSAT par unité (unity_id — Request n'a pas de direction_id direct)."""
        from api.models.ModelRequest import Request as Req

        stmt = (
            select(
                Req.unity_id,
                func.avg(Appreciation.rating).label("avg_rating"),
                func.count(Appreciation.id).label("cnt"),
                func.sum(sa_case((Appreciation.author_type == "internal", 1), else_=0)).label("int_c"),
                func.sum(sa_case((Appreciation.author_type == "external", 1), else_=0)).label("ext_c"),
            )
            .join(Req, Req.id == Appreciation.request_id)
            .where(Appreciation.deleted_at.is_(None))
            .where(Req.deleted_at.is_(None))
            .where(Req.unity_id.isnot(None))
            .group_by(Req.unity_id)
            .order_by(func.avg(Appreciation.rating).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "entity_id": r.unity_id,
                "label": str(r.unity_id),
                "avg": round(float(r.avg_rating or 0), 2),
                "count": r.cnt or 0,
                "internal": r.int_c or 0,
                "external": r.ext_c or 0,
            }
            for r in rows
        ]

    async def csat_monthly(self, *, months: int = 12) -> list[dict]:
        """Évolution mensuelle CSAT sur les N derniers mois (MySQL DATE_FORMAT)."""
        cutoff = datetime.utcnow() - timedelta(days=months * 31)
        month_col = func.date_format(Appreciation.created_at, "%Y-%m").label("month")
        stmt = (
            select(
                month_col,
                func.avg(Appreciation.rating).label("avg_rating"),
                func.count(Appreciation.id).label("cnt"),
            )
            .where(Appreciation.deleted_at.is_(None))
            .where(Appreciation.created_at >= cutoff)
            .group_by(func.date_format(Appreciation.created_at, "%Y-%m"))
            .order_by(func.date_format(Appreciation.created_at, "%Y-%m").asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {"month": r.month, "avg": round(float(r.avg_rating or 0), 2), "count": r.cnt or 0}
            for r in rows
        ]

    async def csat_by_category(self) -> list[dict]:
        """Moyenne CSAT par catégorie de demande (GROUP BY request_category_id + JOIN)."""
        from api.models.ModelRequest import Request as Req
        from api.models.ModelRequestCategory import RequestCategory

        stmt = (
            select(
                Req.request_category_id,
                RequestCategory.name.label("category_name"),
                func.avg(Appreciation.rating).label("avg_rating"),
                func.count(Appreciation.id).label("cnt"),
                func.sum(sa_case((Appreciation.author_type == "internal", 1), else_=0)).label("int_c"),
                func.sum(sa_case((Appreciation.author_type == "external", 1), else_=0)).label("ext_c"),
            )
            .join(Req, Req.id == Appreciation.request_id)
            .join(RequestCategory, RequestCategory.id == Req.request_category_id)
            .where(Appreciation.deleted_at.is_(None))
            .where(Req.deleted_at.is_(None))
            .group_by(Req.request_category_id, RequestCategory.name)
            .order_by(func.avg(Appreciation.rating).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "entity_id": r.request_category_id,
                "label": r.category_name,
                "avg": round(float(r.avg_rating or 0), 2),
                "count": r.cnt or 0,
                "internal": r.int_c or 0,
                "external": r.ext_c or 0,
            }
            for r in rows
        ]
