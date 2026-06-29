"""
Service de statistiques agrégées — EDG Connect.
Requêtes SQL directes (lecture seule) pour alimenter tous les dashboards.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.base_service import BaseService


class StatsService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── KPIs globaux ──────────────────────────────────────────────────────────

    async def global_kpis(self) -> dict:
        """KPIs globaux pour le dashboard principal (tous rôles)."""
        req = await self.session.execute(text("""
            SELECT
                COUNT(*)                                                                                AS total,
                SUM(CASE WHEN rs.code = 'pending'                                    THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN rs.code = 'qualifying'                                 THEN 1 ELSE 0 END) AS qualifying,
                SUM(CASE WHEN rs.code = 'qualified'                                  THEN 1 ELSE 0 END) AS qualified,
                SUM(CASE WHEN rs.code = 'assigned'                                   THEN 1 ELSE 0 END) AS assigned,
                SUM(CASE WHEN rs.code = 'in_progress'                                THEN 1 ELSE 0 END) AS in_progress,
                SUM(CASE WHEN rs.code = 'escalated'                                  THEN 1 ELSE 0 END) AS escalated,
                SUM(CASE WHEN rs.code = 'resolved'                                   THEN 1 ELSE 0 END) AS resolved,
                SUM(CASE WHEN rs.code = 'closed'                                     THEN 1 ELSE 0 END) AS closed,
                SUM(CASE WHEN rs.code = 'cancelled'                                  THEN 1 ELSE 0 END) AS cancelled,
                SUM(CASE WHEN rs.code = 'reopened'                                   THEN 1 ELSE 0 END) AS reopened,
                SUM(CASE WHEN r.in_triage = 1                                        THEN 1 ELSE 0 END) AS in_triage,
                SUM(CASE WHEN r.sla_hours > 0
                         AND TIMESTAMPDIFF(HOUR, r.created_at, NOW()) > r.sla_hours
                         AND rs.code NOT IN ('resolved','closed','cancelled')        THEN 1 ELSE 0 END) AS sla_breached,
                SUM(CASE WHEN DATE(r.created_at) = CURDATE()                         THEN 1 ELSE 0 END) AS created_today,
                SUM(CASE WHEN DATE(r.created_at) = CURDATE()
                         AND rs.code IN ('resolved','closed')                        THEN 1 ELSE 0 END) AS resolved_today
            FROM request r
            JOIN request_status rs ON rs.id = r.request_status_id
            WHERE r.deleted_at IS NULL
        """))
        row = dict(req.mappings().one())

        esc = await self.session.execute(text("""
            SELECT COUNT(*) AS open_escalations
            FROM escalation
            WHERE escalation_status = 'open' AND deleted_at IS NULL
        """))
        esc_row = dict(esc.mappings().one())

        csat = await self.session.execute(text("""
            SELECT
                COALESCE(AVG(rating), 0)  AS avg_rating,
                COUNT(*)                  AS total_ratings
            FROM appreciation
            WHERE deleted_at IS NULL
        """))
        csat_row = dict(csat.mappings().one())

        total = row["total"] or 0
        resolved = (row["resolved"] or 0) + (row["closed"] or 0)

        return {
            "total_requests":    total,
            "pending":           row["pending"] or 0,
            "qualifying":        row["qualifying"] or 0,
            "qualified":         row["qualified"] or 0,
            "assigned":          row["assigned"] or 0,
            "in_progress":       row["in_progress"] or 0,
            "escalated":         row["escalated"] or 0,
            "resolved":          row["resolved"] or 0,
            "closed":            row["closed"] or 0,
            "cancelled":         row["cancelled"] or 0,
            "reopened":          row["reopened"] or 0,
            "in_triage":         row["in_triage"] or 0,
            "sla_breached":      row["sla_breached"] or 0,
            "created_today":     row["created_today"] or 0,
            "resolved_today":    row["resolved_today"] or 0,
            "resolution_rate":   round(resolved / total * 100, 1) if total else 0.0,
            "open_escalations":  esc_row["open_escalations"] or 0,
            "avg_satisfaction":  round(float(csat_row["avg_rating"]), 2),
            "total_ratings":     csat_row["total_ratings"] or 0,
        }

    # ── Breakdowns ────────────────────────────────────────────────────────────

    async def requests_by_direction(self) -> list[dict]:
        """Requêtes groupées par direction (avec nom)."""
        result = await self.session.execute(text("""
            SELECT
                r.direction_id,
                COALESCE(d.name, 'Non assignée') AS direction_name,
                COUNT(*)                          AS total,
                SUM(CASE WHEN rs.code IN ('resolved','closed')
                                                  THEN 1 ELSE 0 END) AS resolved,
                SUM(CASE WHEN rs.code IN ('pending','qualifying','qualified',
                         'assigned','in_progress','escalated','reopened')
                                                  THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN r.sla_hours > 0
                         AND TIMESTAMPDIFF(HOUR, r.created_at, NOW()) > r.sla_hours
                         AND rs.code NOT IN ('resolved','closed','cancelled')
                                                  THEN 1 ELSE 0 END) AS sla_breached
            FROM request r
            JOIN request_status rs ON rs.id = r.request_status_id
            LEFT JOIN direction d ON d.id = r.direction_id AND d.deleted_at IS NULL
            WHERE r.deleted_at IS NULL
            GROUP BY r.direction_id, d.name
            ORDER BY total DESC
        """))
        return [dict(row) for row in result.mappings().all()]

    async def requests_by_unit(self) -> list[dict]:
        """Requêtes groupées par unité (avec nom de direction)."""
        result = await self.session.execute(text("""
            SELECT
                r.unit_id,
                COALESCE(u.name, 'Non assignée')   AS unit_name,
                COALESCE(d.name, '')               AS direction_name,
                COUNT(*)                           AS total,
                SUM(CASE WHEN rs.code IN ('resolved','closed')
                                                   THEN 1 ELSE 0 END) AS resolved,
                SUM(CASE WHEN rs.code IN ('pending','qualifying','qualified',
                         'assigned','in_progress','escalated','reopened')
                                                   THEN 1 ELSE 0 END) AS active
            FROM request r
            JOIN request_status rs ON rs.id = r.request_status_id
            LEFT JOIN unit u      ON u.id = r.unit_id      AND u.deleted_at IS NULL
            LEFT JOIN direction d ON d.id = u.direction_id AND d.deleted_at IS NULL
            WHERE r.deleted_at IS NULL
            GROUP BY r.unit_id, u.name, d.name
            ORDER BY total DESC
        """))
        return [dict(row) for row in result.mappings().all()]

    async def requests_by_period(self, days: int = 30) -> list[dict]:
        """Évolution quotidienne sur les N derniers jours (pour graphiques)."""
        result = await self.session.execute(
            text("""
                SELECT
                    DATE(r.created_at)   AS day,
                    COUNT(*)             AS total,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')
                             THEN 1 ELSE 0 END) AS resolved
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE r.deleted_at IS NULL
                  AND r.created_at >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
                GROUP BY DATE(r.created_at)
                ORDER BY day ASC
            """),
            {"days": days},
        )
        return [dict(row) for row in result.mappings().all()]

    async def requests_by_category(self) -> list[dict]:
        """Breakdown des requêtes par catégorie."""
        result = await self.session.execute(text("""
            SELECT
                rc.code                                                                    AS category,
                COUNT(*)                                                                   AS total,
                SUM(CASE WHEN rs.code IN ('resolved','closed')
                         THEN 1 ELSE 0 END)                                                AS resolved,
                SUM(CASE WHEN rs.code IN ('pending','qualifying','qualified',
                         'assigned','in_progress','escalated','reopened')
                         THEN 1 ELSE 0 END)                                                AS active,
                ROUND(
                    SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END)
                    * 100.0 / COUNT(*), 1
                )                                                                          AS resolution_rate
            FROM request r
            JOIN request_status rs  ON rs.id = r.request_status_id
            JOIN request_category rc ON rc.id = r.request_category_id
            WHERE r.deleted_at IS NULL
            GROUP BY rc.code
            ORDER BY total DESC
        """))
        return [dict(row) for row in result.mappings().all()]

    async def requests_by_priority(self) -> list[dict]:
        """Breakdown par priorité."""
        result = await self.session.execute(text("""
            SELECT
                pd.slug                                                                     AS priority,
                COUNT(*)                                                                    AS total,
                SUM(CASE WHEN rs.code IN ('resolved','closed')
                         THEN 1 ELSE 0 END)                                                 AS resolved,
                SUM(CASE WHEN r.sla_hours > 0
                         AND TIMESTAMPDIFF(HOUR, r.created_at, NOW()) > r.sla_hours
                         AND rs.code NOT IN ('resolved','closed','cancelled')
                         THEN 1 ELSE 0 END)                                                 AS sla_breached
            FROM request r
            JOIN request_status rs       ON rs.id = r.request_status_id
            JOIN priority_definition pd  ON pd.id = r.priority_definition_id
            WHERE r.deleted_at IS NULL
            GROUP BY pd.slug
            ORDER BY FIELD(pd.slug, 'critical','high','medium','low')
        """))
        return [dict(row) for row in result.mappings().all()]

    # ── Performance agents ────────────────────────────────────────────────────

    async def agent_performance(
        self,
        direction_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Performance par agent : requêtes assignées, résolues, temps moyen."""
        conditions = ["a.deleted_at IS NULL", "a.role IN ('agent','chief')"]
        params: dict = {"limit": limit}
        if direction_id:
            conditions.append("a.direction_id = :direction_id")
            params["direction_id"] = direction_id
        if unit_id:
            conditions.append("a.unit_id = :unit_id")
            params["unit_id"] = unit_id

        where = " AND ".join(conditions)
        result = await self.session.execute(
            text(f"""
                SELECT
                    a.id              AS agent_id,
                    a.uuid            AS agent_uuid,
                    a.name            AS agent_name,
                    a.availability,
                    a.direction_id,
                    COALESCE(d.name,'') AS direction_name,
                    COUNT(r.id)                          AS assigned_total,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')
                             THEN 1 ELSE 0 END)           AS resolved_total,
                    SUM(CASE WHEN rs.code IN ('pending','qualifying','qualified',
                             'assigned','in_progress','escalated','reopened')
                             THEN 1 ELSE 0 END)           AS active_total,
                    ROUND(AVG(
                        CASE WHEN r.resolved_at IS NOT NULL
                             THEN TIMESTAMPDIFF(HOUR, r.created_at, r.resolved_at)
                        END
                    ), 1)                                 AS avg_resolution_hours
                FROM account a
                LEFT JOIN direction d  ON d.id = a.direction_id AND d.deleted_at IS NULL
                LEFT JOIN request r    ON r.assignee_id = a.id  AND r.deleted_at IS NULL
                LEFT JOIN request_status rs ON rs.id = r.request_status_id
                WHERE {where}
                GROUP BY a.id, a.uuid, a.name, a.availability, a.direction_id, d.name
                ORDER BY resolved_total DESC
                LIMIT :limit
            """),
            params,
        )
        return [dict(row) for row in result.mappings().all()]

    # ── Stats personnelles agent ──────────────────────────────────────────────

    async def my_stats(self, agent_id: int) -> dict:
        """Stats personnelles d'un agent : ses tickets assignés, résolus, SLA, temps moyen."""
        result = await self.session.execute(text("""
            SELECT
                COUNT(r.id)                                                        AS assigned_total,
                SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END) AS resolved_total,
                SUM(CASE WHEN rs.code IN ('pending','qualifying','qualified',
                         'assigned','in_progress','escalated','reopened')
                         THEN 1 ELSE 0 END)                                        AS active_total,
                SUM(CASE WHEN rs.code IN ('pending','qualifying','qualified',
                         'assigned','in_progress','escalated','reopened')
                         AND r.sla_deadline IS NOT NULL
                         AND r.sla_deadline < NOW()
                         THEN 1 ELSE 0 END)                                        AS sla_breached,
                ROUND(AVG(
                    CASE WHEN r.resolved_at IS NOT NULL
                         THEN TIMESTAMPDIFF(HOUR, r.created_at, r.resolved_at)
                    END
                ), 1)                                                              AS avg_resolution_hours,
                ROUND(
                    100.0 * SUM(CASE WHEN rs.code IN ('resolved','closed')
                                          AND (r.resolved_at IS NULL OR r.resolved_at <= r.sla_deadline)
                                     THEN 1 ELSE 0 END)
                    / NULLIF(SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END), 0)
                , 1)                                                               AS sla_rate
            FROM request r
            JOIN request_status rs ON rs.id = r.request_status_id
            WHERE r.assignee_id = :agent_id
              AND r.deleted_at IS NULL
        """), {"agent_id": agent_id})
        row = result.mappings().one_or_none()
        return dict(row) if row else {
            "assigned_total": 0, "resolved_total": 0, "active_total": 0,
            "sla_breached": 0, "avg_resolution_hours": None, "sla_rate": None,
        }

    # ── Escalades ─────────────────────────────────────────────────────────────

    async def escalation_stats(self) -> dict:
        """Stats des escalades par statut et niveau."""
        result = await self.session.execute(text("""
            SELECT
                COUNT(*)                                                                   AS total,
                SUM(CASE WHEN escalation_status = 'open'         THEN 1 ELSE 0 END)       AS open,
                SUM(CASE WHEN escalation_status = 'acknowledged' THEN 1 ELSE 0 END)       AS acknowledged,
                SUM(CASE WHEN escalation_status = 'resolved'     THEN 1 ELSE 0 END)       AS resolved,
                SUM(CASE WHEN escalation_status = 'cancelled'    THEN 1 ELSE 0 END)       AS cancelled,
                SUM(CASE WHEN level = 'L1'                       THEN 1 ELSE 0 END)       AS level_l1,
                SUM(CASE WHEN level = 'L2'                       THEN 1 ELSE 0 END)       AS level_l2,
                SUM(CASE WHEN level = 'L3'                       THEN 1 ELSE 0 END)       AS level_l3,
                SUM(CASE WHEN DATE(created_at) = CURDATE()       THEN 1 ELSE 0 END)       AS created_today
            FROM escalation
            WHERE deleted_at IS NULL
        """))
        return dict(result.mappings().one())

    # ── SLA ───────────────────────────────────────────────────────────────────

    async def sla_compliance(
        self,
        direction_id: Optional[int] = None,
    ) -> dict:
        """Conformité SLA globale ou par direction."""
        conditions = ["r.deleted_at IS NULL", "r.sla_hours > 0"]
        params: dict = {}
        if direction_id:
            conditions.append("r.direction_id = :direction_id")
            params["direction_id"] = direction_id

        where = " AND ".join(conditions)
        result = await self.session.execute(
            text(f"""
                SELECT
                    COUNT(*)  AS total_with_sla,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')
                             AND r.resolved_at IS NOT NULL
                             AND r.resolved_at <= DATE_ADD(r.created_at, INTERVAL r.sla_hours HOUR) THEN 1 ELSE 0 END) AS resolved_in_sla,
                    SUM(CASE WHEN TIMESTAMPDIFF(HOUR, r.created_at, NOW()) > r.sla_hours
                             AND rs.code NOT IN ('resolved','closed','cancelled')
                                                             THEN 1 ELSE 0 END) AS currently_breached,
                    SUM(CASE WHEN r.resolved_at IS NOT NULL
                             AND r.resolved_at > DATE_ADD(r.created_at, INTERVAL r.sla_hours HOUR) THEN 1 ELSE 0 END) AS resolved_late,
                    ROUND(AVG(
                        CASE WHEN r.resolved_at IS NOT NULL
                             THEN TIMESTAMPDIFF(MINUTE, r.created_at, r.resolved_at)
                        END
                    ), 0)                                     AS avg_resolution_minutes
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE {where}
            """),
            params,
        )
        row = dict(result.mappings().one())
        total = row["total_with_sla"] or 0
        in_sla = row["resolved_in_sla"] or 0
        return {
            "total_with_sla":       total,
            "resolved_in_sla":      in_sla,
            "currently_breached":   row["currently_breached"] or 0,
            "resolved_late":        row["resolved_late"] or 0,
            "compliance_rate":      round(in_sla / total * 100, 1) if total else 100.0,
            "avg_resolution_minutes": row["avg_resolution_minutes"] or 0,
            "direction_id":         direction_id,
        }

    # ── Dashboard complet ─────────────────────────────────────────────────────

    async def dashboard_summary(
        self,
        direction_id: Optional[int] = None,
        unit_id: Optional[int] = None,
    ) -> dict:
        """
        Résumé complet pour un dashboard de rôle.
        Réduit au périmètre direction/unité si fourni.
        """
        scope_conditions = "r.deleted_at IS NULL"
        params: dict = {}
        if direction_id:
            scope_conditions += " AND r.direction_id = :direction_id"
            params["direction_id"] = direction_id
        if unit_id:
            scope_conditions += " AND r.unit_id = :unit_id"
            params["unit_id"] = unit_id

        req = await self.session.execute(
            text(f"""
                SELECT
                    COUNT(*)                                                    AS total,
                    SUM(CASE WHEN rs.code IN ('pending','qualifying',
                             'qualified','assigned','in_progress','reopened')
                                                                THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN rs.code = 'escalated'         THEN 1 ELSE 0 END) AS escalated,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')
                                                                THEN 1 ELSE 0 END) AS resolved,
                    SUM(CASE WHEN r.in_triage = 1               THEN 1 ELSE 0 END) AS in_triage,
                    SUM(CASE WHEN r.sla_hours > 0
                             AND TIMESTAMPDIFF(HOUR, r.created_at, NOW()) > r.sla_hours
                             AND rs.code NOT IN ('resolved','closed','cancelled')
                                                                THEN 1 ELSE 0 END) AS sla_breached,
                    SUM(CASE WHEN DATE(r.created_at) = CURDATE() THEN 1 ELSE 0 END) AS created_today,
                    SUM(CASE WHEN DATE(r.created_at) = CURDATE()
                             AND rs.code IN ('resolved','closed')
                                                                THEN 1 ELSE 0 END) AS resolved_today
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                WHERE {scope_conditions}
            """),
            params,
        )
        row = dict(req.mappings().one())
        total = row["total"] or 0
        resolved = row["resolved"] or 0

        return {
            "total":          total,
            "active":         row["active"] or 0,
            "escalated":      row["escalated"] or 0,
            "resolved":       resolved,
            "in_triage":      row["in_triage"] or 0,
            "sla_breached":   row["sla_breached"] or 0,
            "created_today":  row["created_today"] or 0,
            "resolved_today": row["resolved_today"] or 0,
            "resolution_rate": round(resolved / total * 100, 1) if total else 0.0,
            "direction_id":   direction_id,
            "unit_id":        unit_id,
        }
