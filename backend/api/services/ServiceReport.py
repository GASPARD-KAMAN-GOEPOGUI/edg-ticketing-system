"""
Service de génération de rapports — EDG Connect.
Produit les données brutes pour les rapports journaliers, mensuels,
par service (unity) et par agent.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.base_service import BaseService

logger = logging.getLogger(__name__)


class ReportService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Rapport journalier ────────────────────────────────────────────────────

    async def daily_report(self, report_date: Optional[date] = None) -> dict:
        """
        Rapport complet pour une journée donnée (défaut = aujourd'hui).
        Retourne : résumé + breakdown par statut + breakdown par catégorie + top agents.
        """
        d = report_date or date.today()
        d_str = d.isoformat()

        summary = await self.session.execute(
            text("""
                SELECT
                    COUNT(*)                                                           AS total_created,
                    SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END) AS total_resolved,
                    SUM(CASE WHEN rs.code = 'escalated'            THEN 1 ELSE 0 END) AS total_escalated,
                    SUM(CASE WHEN rs.code = 'cancelled'            THEN 1 ELSE 0 END) AS total_cancelled,
                    SUM(CASE WHEN r.is_external = 1                THEN 1 ELSE 0 END) AS external_count,
                    SUM(CASE WHEN r.sla_breached = 1               THEN 1 ELSE 0 END) AS sla_breached,
                    ROUND(AVG(
                        CASE WHEN r.resolved_at IS NOT NULL
                             THEN TIMESTAMPDIFF(MINUTE, r.created_at, r.resolved_at)
                        END
                    ), 0) AS avg_resolution_min
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE r.deleted_at IS NULL
                  AND DATE(r.created_at) = :d
            """),
            {"d": d_str},
        )
        row = dict(summary.mappings().one())

        by_category = await self.session.execute(
            text("""
                SELECT rc.code AS category, COUNT(*) AS total
                FROM request r
                JOIN request_category rc ON rc.id = r.request_category_id
                WHERE r.deleted_at IS NULL AND DATE(r.created_at) = :d
                GROUP BY rc.code ORDER BY total DESC
            """),
            {"d": d_str},
        )

        by_priority = await self.session.execute(
            text("""
                SELECT pd.slug AS priority, COUNT(*) AS total
                FROM request r
                JOIN priority_definition pd ON pd.id = r.priority_definition_id
                WHERE r.deleted_at IS NULL AND DATE(r.created_at) = :d
                GROUP BY pd.slug ORDER BY total DESC
            """),
            {"d": d_str},
        )

        top_agents = await self.session.execute(
            text("""
                SELECT a.name AS agent_name, COUNT(*) AS resolved_count
                FROM request r
                JOIN account a ON a.id = r.assignee_id
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE r.deleted_at IS NULL
                  AND DATE(r.resolved_at) = :d
                  AND rs.code IN ('resolved','closed')
                GROUP BY a.id, a.name
                ORDER BY resolved_count DESC
                LIMIT 10
            """),
            {"d": d_str},
        )

        total = row["total_created"] or 0
        resolved = row["total_resolved"] or 0
        return {
            "report_type": "daily",
            "date": d_str,
            "summary": {
                "total_created": total,
                "total_resolved": resolved,
                "total_escalated": row["total_escalated"] or 0,
                "total_cancelled": row["total_cancelled"] or 0,
                "external_count": row["external_count"] or 0,
                "sla_breached": row["sla_breached"] or 0,
                "resolution_rate": round(resolved / total * 100, 1) if total else 0.0,
                "avg_resolution_min": int(row["avg_resolution_min"] or 0),
            },
            "by_category": [dict(r) for r in by_category.mappings().all()],
            "by_priority": [dict(r) for r in by_priority.mappings().all()],
            "top_agents": [dict(r) for r in top_agents.mappings().all()],
        }

    # ── Rapport mensuel ───────────────────────────────────────────────────────

    async def monthly_report(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> dict:
        """
        Rapport mensuel : évolution jour par jour + résumé + breakdown par catégorie.
        """
        from datetime import date as dt_date
        today = dt_date.today()
        y = year or today.year
        m = month or today.month

        import calendar
        last_day = calendar.monthrange(y, m)[1]
        start = f"{y:04d}-{m:02d}-01"
        end = f"{y:04d}-{m:02d}-{last_day:02d}"

        summary = await self.session.execute(
            text("""
                SELECT
                    COUNT(*)                                                           AS total_created,
                    SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END) AS total_resolved,
                    SUM(CASE WHEN rs.code = 'escalated'            THEN 1 ELSE 0 END) AS total_escalated,
                    SUM(CASE WHEN r.sla_breached = 1               THEN 1 ELSE 0 END) AS sla_breached,
                    ROUND(AVG(
                        CASE WHEN r.resolved_at IS NOT NULL
                             THEN TIMESTAMPDIFF(MINUTE, r.created_at, r.resolved_at)
                        END
                    ), 0) AS avg_resolution_min
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE r.deleted_at IS NULL
                  AND DATE(r.created_at) BETWEEN :start AND :end
            """),
            {"start": start, "end": end},
        )
        row = dict(summary.mappings().one())

        daily = await self.session.execute(
            text("""
                SELECT
                    DATE(r.created_at) AS day,
                    COUNT(*) AS created,
                    SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END) AS resolved
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE r.deleted_at IS NULL
                  AND DATE(r.created_at) BETWEEN :start AND :end
                GROUP BY DATE(r.created_at)
                ORDER BY day ASC
            """),
            {"start": start, "end": end},
        )

        by_category = await self.session.execute(
            text("""
                SELECT rc.code AS category, COUNT(*) AS total,
                    SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END) AS resolved
                FROM request r
                JOIN request_category rc ON rc.id = r.request_category_id
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE r.deleted_at IS NULL
                  AND DATE(r.created_at) BETWEEN :start AND :end
                GROUP BY rc.code ORDER BY total DESC
            """),
            {"start": start, "end": end},
        )

        sla = await self.session.execute(
            text("""
                SELECT
                    COUNT(*) AS total_with_sla,
                    SUM(CASE WHEN r.resolved_at IS NOT NULL
                             AND r.resolved_at <= DATE_ADD(r.created_at, INTERVAL r.sla_hours HOUR)
                             THEN 1 ELSE 0 END) AS resolved_in_sla
                FROM request r
                WHERE r.deleted_at IS NULL AND r.sla_hours > 0
                  AND DATE(r.created_at) BETWEEN :start AND :end
            """),
            {"start": start, "end": end},
        )
        sla_row = dict(sla.mappings().one())
        sla_total = sla_row["total_with_sla"] or 0
        sla_ok = sla_row["resolved_in_sla"] or 0

        total = row["total_created"] or 0
        resolved = row["total_resolved"] or 0
        return {
            "report_type": "monthly",
            "year": y,
            "month": m,
            "period": f"{start} → {end}",
            "summary": {
                "total_created": total,
                "total_resolved": resolved,
                "total_escalated": row["total_escalated"] or 0,
                "sla_breached": row["sla_breached"] or 0,
                "resolution_rate": round(resolved / total * 100, 1) if total else 0.0,
                "avg_resolution_min": int(row["avg_resolution_min"] or 0),
                "sla_compliance_rate": round(sla_ok / sla_total * 100, 1) if sla_total else 100.0,
            },
            "daily_evolution": [dict(r) for r in daily.mappings().all()],
            "by_category": [dict(r) for r in by_category.mappings().all()],
        }

    # ── Rapport par agent ─────────────────────────────────────────────────────

    async def agent_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        unity_id: Optional[int] = None,
    ) -> list[dict]:
        """
        Performance de chaque agent sur une période.
        """
        from datetime import date as dt_date
        today = dt_date.today()
        s = (start_date or (today - timedelta(days=30))).isoformat()
        e = (end_date or today).isoformat()

        conditions = "r.deleted_at IS NULL AND DATE(r.created_at) BETWEEN :start AND :end"
        params: dict = {"start": s, "end": e}
        if unity_id:
            conditions += " AND r.unity_id = :unity_id"
            params["unity_id"] = unity_id

        result = await self.session.execute(
            text(f"""
                SELECT
                    a.id          AS agent_id,
                    a.name        AS agent_name,
                    a.role        AS agent_role,
                    u.label       AS unity_label,
                    COUNT(r.id)   AS assigned_total,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')  THEN 1 ELSE 0 END) AS resolved_total,
                    SUM(CASE WHEN rs.code = 'escalated'            THEN 1 ELSE 0 END) AS escalated_total,
                    ROUND(AVG(
                        CASE WHEN r.resolved_at IS NOT NULL
                             THEN TIMESTAMPDIFF(HOUR, r.created_at, r.resolved_at)
                        END
                    ), 1) AS avg_resolution_hours,
                    ROUND(
                        SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END)
                        * 100.0 / NULLIF(COUNT(r.id), 0), 1
                    ) AS resolution_rate
                FROM account a
                LEFT JOIN unity u ON u.id = a.unity_id AND u.deleted_at IS NULL
                LEFT JOIN request r ON r.assignee_id = a.id AND {conditions}
                LEFT JOIN request_status rs ON rs.id = r.request_status_id
                WHERE a.deleted_at IS NULL AND a.role IN ('agent','chief')
                GROUP BY a.id, a.name, a.role, u.label
                ORDER BY resolved_total DESC
            """),
            params,
        )
        return [dict(r) for r in result.mappings().all()]

    # ── Rapport par service (unity) ───────────────────────────────────────────

    async def unity_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """
        Tickets par unité organisationnelle sur une période.
        """
        from datetime import date as dt_date
        today = dt_date.today()
        s = (start_date or (today - timedelta(days=30))).isoformat()
        e = (end_date or today).isoformat()

        result = await self.session.execute(
            text("""
                SELECT
                    u.id           AS unity_id,
                    u.label        AS unity_label,
                    u.codename     AS unity_codename,
                    COUNT(r.id)    AS total,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')  THEN 1 ELSE 0 END) AS resolved,
                    SUM(CASE WHEN rs.code IN ('new','qualifying','qualified',
                             'assigned','in_progress','escalated','reopened')
                                                                   THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN r.sla_breached = 1               THEN 1 ELSE 0 END) AS sla_breached,
                    ROUND(
                        SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END)
                        * 100.0 / NULLIF(COUNT(r.id), 0), 1
                    ) AS resolution_rate
                FROM unity u
                LEFT JOIN request r
                    ON r.unity_id = u.id
                    AND r.deleted_at IS NULL
                    AND DATE(r.created_at) BETWEEN :start AND :end
                LEFT JOIN request_status rs ON rs.id = r.request_status_id
                WHERE u.deleted_at IS NULL
                GROUP BY u.id, u.label, u.codename
                ORDER BY total DESC
            """),
            {"start": s, "end": e},
        )
        return [dict(r) for r in result.mappings().all()]

    # ── Rapport CSAT ─────────────────────────────────────────────────────────

    async def csat_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        unity_id: Optional[int] = None,
    ) -> dict:
        """
        Rapport CSAT (satisfaction client) sur une période.
        Retourne : résumé global + breakdown par note + par agent + par catégorie + évolution mensuelle.
        """
        from datetime import date as dt_date
        today = dt_date.today()
        s = (start_date or (today - timedelta(days=30))).isoformat()
        e = (end_date or today).isoformat()

        base_cond = (
            "ap.deleted_at IS NULL AND r.deleted_at IS NULL "
            "AND DATE(ap.created_at) BETWEEN :start AND :end"
        )
        params: dict = {"start": s, "end": e}
        unity_filter = ""
        if unity_id:
            unity_filter = " AND r.unity_id = :unity_id"
            params["unity_id"] = unity_id

        # Résumé global
        summary_res = await self.session.execute(
            text(f"""
                SELECT
                    COUNT(*)                                AS total_ratings,
                    ROUND(AVG(ap.rating), 2)               AS avg_rating,
                    SUM(CASE WHEN ap.rating >= 4 THEN 1 ELSE 0 END) AS satisfied_count,
                    SUM(CASE WHEN ap.rating <= 2 THEN 1 ELSE 0 END) AS dissatisfied_count,
                    SUM(CASE WHEN ap.resolved_confirmed = 1 THEN 1 ELSE 0 END) AS resolved_confirmed_count
                FROM appreciation ap
                JOIN request r ON r.id = ap.request_id
                WHERE {base_cond}{unity_filter}
            """),
            params,
        )
        summary_row = dict(summary_res.mappings().one())
        total = summary_row["total_ratings"] or 0

        # Distribution par note (1 à 5)
        dist_res = await self.session.execute(
            text(f"""
                SELECT ap.rating, COUNT(*) AS count
                FROM appreciation ap
                JOIN request r ON r.id = ap.request_id
                WHERE {base_cond}{unity_filter}
                GROUP BY ap.rating
                ORDER BY ap.rating ASC
            """),
            params,
        )

        # Breakdown par agent
        by_agent_res = await self.session.execute(
            text(f"""
                SELECT
                    a.id              AS agent_id,
                    a.name            AS agent_name,
                    u.label           AS unity_label,
                    COUNT(ap.id)      AS total_ratings,
                    ROUND(AVG(ap.rating), 2) AS avg_rating,
                    SUM(CASE WHEN ap.rating >= 4 THEN 1 ELSE 0 END) AS satisfied_count
                FROM appreciation ap
                JOIN request r ON r.id = ap.request_id
                JOIN account a ON a.id = r.assignee_id
                LEFT JOIN unity u ON u.id = a.unity_id AND u.deleted_at IS NULL
                WHERE {base_cond}{unity_filter}
                GROUP BY a.id, a.name, u.label
                ORDER BY avg_rating DESC, total_ratings DESC
            """),
            params,
        )

        # Breakdown par catégorie
        by_cat_res = await self.session.execute(
            text(f"""
                SELECT
                    rc.code           AS category,
                    COUNT(ap.id)      AS total_ratings,
                    ROUND(AVG(ap.rating), 2) AS avg_rating
                FROM appreciation ap
                JOIN request r ON r.id = ap.request_id
                JOIN request_category rc ON rc.id = r.request_category_id
                WHERE {base_cond}{unity_filter}
                GROUP BY rc.code
                ORDER BY avg_rating DESC
            """),
            params,
        )

        # Évolution mensuelle
        monthly_res = await self.session.execute(
            text(f"""
                SELECT
                    DATE_FORMAT(ap.created_at, '%Y-%m') AS month,
                    COUNT(ap.id)                         AS total_ratings,
                    ROUND(AVG(ap.rating), 2)             AS avg_rating
                FROM appreciation ap
                JOIN request r ON r.id = ap.request_id
                WHERE {base_cond}{unity_filter}
                GROUP BY DATE_FORMAT(ap.created_at, '%Y-%m')
                ORDER BY month ASC
            """),
            params,
        )

        satisfied = summary_row["satisfied_count"] or 0
        confirmed = summary_row["resolved_confirmed_count"] or 0
        return {
            "report_type": "csat",
            "period": f"{s} → {e}",
            "unity_id": unity_id,
            "summary": {
                "total_ratings": total,
                "avg_rating": float(summary_row["avg_rating"] or 0),
                "satisfaction_rate": round(satisfied / total * 100, 1) if total else 0.0,
                "resolved_confirmed_rate": round(confirmed / total * 100, 1) if total else 0.0,
                "satisfied_count": satisfied,
                "dissatisfied_count": summary_row["dissatisfied_count"] or 0,
            },
            "by_rating": [dict(r) for r in dist_res.mappings().all()],
            "by_agent": [dict(r) for r in by_agent_res.mappings().all()],
            "by_category": [dict(r) for r in by_cat_res.mappings().all()],
            "monthly_evolution": [dict(r) for r in monthly_res.mappings().all()],
        }

    # ── Rapport SLA global ────────────────────────────────────────────────────

    async def sla_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """Taux de conformité SLA, résolutions tardives, temps moyen."""
        from datetime import date as dt_date
        today = dt_date.today()
        s = (start_date or (today - timedelta(days=30))).isoformat()
        e = (end_date or today).isoformat()

        result = await self.session.execute(
            text("""
                SELECT
                    COUNT(*) AS total_with_sla,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')
                             AND r.resolved_at IS NOT NULL
                             AND r.resolved_at <= DATE_ADD(r.created_at, INTERVAL r.sla_hours HOUR)
                             THEN 1 ELSE 0 END) AS resolved_in_sla,
                    SUM(CASE WHEN r.sla_breached = 1 AND rs.code NOT IN ('resolved','closed','cancelled')
                             THEN 1 ELSE 0 END) AS currently_breached,
                    SUM(CASE WHEN r.resolved_at IS NOT NULL
                             AND r.resolved_at > DATE_ADD(r.created_at, INTERVAL r.sla_hours HOUR)
                             THEN 1 ELSE 0 END) AS resolved_late,
                    ROUND(AVG(
                        CASE WHEN r.resolved_at IS NOT NULL
                             THEN TIMESTAMPDIFF(MINUTE, r.created_at, r.resolved_at)
                        END
                    ), 0) AS avg_resolution_min
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE r.deleted_at IS NULL AND r.sla_hours > 0
                  AND DATE(r.created_at) BETWEEN :start AND :end
            """),
            {"start": s, "end": e},
        )
        row = dict(result.mappings().one())
        total = row["total_with_sla"] or 0
        in_sla = row["resolved_in_sla"] or 0
        return {
            "report_type": "sla",
            "period": f"{s} → {e}",
            "total_with_sla": total,
            "resolved_in_sla": in_sla,
            "currently_breached": row["currently_breached"] or 0,
            "resolved_late": row["resolved_late"] or 0,
            "compliance_rate": round(in_sla / total * 100, 1) if total else 100.0,
            "avg_resolution_min": int(row["avg_resolution_min"] or 0),
        }
