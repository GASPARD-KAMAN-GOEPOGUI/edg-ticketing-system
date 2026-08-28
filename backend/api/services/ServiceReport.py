"""
Service de génération de rapports — EDG Support.
Produit les données brutes pour les rapports journaliers, mensuels,
par service (unity) et par agent.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from api.models.ModelOrganigram import Organigram
from api.models.ModelUnity import Unity
from api.services.base_service import BaseService

logger = logging.getLogger(__name__)

ACTIVE_STATUS_CODES = {
    "new",
    "qualifying",
    "qualified",
    "assigned",
    "in_progress",
    "pending",
    "pending_validation",
    "escalated",
    "reopened",
}
BACKLOG_STATUS_CODES = {
    "new",
    "qualifying",
    "qualified",
    "assigned",
    "pending",
    "pending_validation",
    "escalated",
    "reopened",
}
RESOLVED_STATUS_CODES = {"resolved", "closed"}
URGENT_PRIORITY_CODES = {"urgent", "high"}
DEFAULT_INACTIVE_DAYS = 3

DECISION_GROUPS = {
    "global",
    "executive",
    "direction",
    "service",
    "status",
    "category",
    "priority",
    "assignee",
    "period",
    "audit",
}

def _decision_kpi(
    key: str,
    definition: str,
    formula: str,
    source: str,
    aggregation: str,
    scope: str = "période + filtres actifs",
) -> dict[str, str]:
    return {
        "key": key,
        "definition": definition,
        "formula": formula,
        "source": source,
        "scope": scope,
        "aggregation": aggregation,
    }


DECISION_KPI_CATALOG = [
    _decision_kpi("total_tickets", "Tickets distincts du périmètre.", "COUNT(DISTINCT request.id)", "request.id", "somme des tickets uniques"),
    _decision_kpi("new_tickets", "Tickets nouveaux.", "status = new", "request_status.code", "somme"),
    _decision_kpi("qualifying_tickets", "Tickets à qualifier ou en triage.", "status = qualifying OR request.in_triage = true", "request_status.code, request.in_triage", "somme"),
    _decision_kpi("assigned_tickets", "Tickets affectés mais pas encore en traitement.", "status = assigned", "request_status.code", "somme"),
    _decision_kpi("open_tickets", "Tickets actifs non terminés.", "status IN active statuses", "request_status.code", "somme"),
    _decision_kpi("in_progress_tickets", "Tickets en cours de traitement.", "status = in_progress", "request_status.code", "somme"),
    _decision_kpi("pending_validation_tickets", "Tickets en attente de validation.", "status IN pending, pending_validation", "request_status.code", "somme"),
    _decision_kpi("resolved_tickets", "Tickets résolus non clôturés.", "status = resolved", "request_status.code", "somme"),
    _decision_kpi("closed_tickets", "Tickets clôturés.", "status = closed", "request_status.code", "somme"),
    _decision_kpi("escalated_tickets", "Tickets actuellement escaladés ou ayant une escalade tracée.", "status = escalated OR escalation_events > 0", "request_status.code, workflow_detail.event_type", "somme par ticket unique"),
    _decision_kpi("reopened_tickets", "Tickets actuellement réouverts ou ayant une réouverture tracée.", "status = reopened OR reopen_events > 0", "request_status.code, workflow_detail.event_type", "somme par ticket unique"),
    _decision_kpi("backlog_tickets", "Tickets actifs hors traitement final.", "status IN backlog statuses", "request_status.code", "somme"),
    _decision_kpi("critical_tickets", "Tickets de priorité critique.", "priority = critical", "priority_definition.slug", "somme"),
    _decision_kpi("urgent_tickets", "Tickets de priorité urgente/haute.", "priority IN urgent, high", "priority_definition.slug", "somme"),
    _decision_kpi("overdue_tickets", "Tickets en retard métier.", "request.sla_breached = true", "request.sla_breached", "somme"),
    _decision_kpi("sla_breached_tickets", "Tickets hors SLA.", "request.sla_breached = true", "request.sla_breached", "somme"),
    _decision_kpi("sla_respected_tickets", "Tickets avec SLA renseigné et non dépassé.", "sla_hours > 0 AND sla_breached = false", "request.sla_hours, request.sla_breached", "somme"),
    _decision_kpi("sla_compliance_rate", "Taux de respect SLA.", "sla_respected_tickets / (sla_respected_tickets + sla_breached_tickets) * 100", "KPI consolidés", "recalcul sur totaux"),
    _decision_kpi("resolution_rate", "Taux de résolution.", "(resolved_tickets + closed_tickets) / total_tickets * 100", "KPI consolidés", "recalcul sur totaux"),
    _decision_kpi("closure_rate", "Taux de clôture.", "closed_tickets / total_tickets * 100", "KPI consolidés", "recalcul sur totaux"),
    _decision_kpi("avg_qualification_hours", "Délai moyen avant qualification/orientation.", "AVG(created_at -> first qualifying|qualified|assigned event) / 60", "request.created_at, workflow_detail.created_at", "moyenne pondérée traçable"),
    _decision_kpi("avg_assignment_hours", "Délai moyen avant affectation.", "AVG(created_at -> first assigned|reassigned_service event) / 60", "request.created_at, workflow_detail.created_at", "moyenne pondérée traçable"),
    _decision_kpi("avg_first_response_hours", "Délai moyen de première prise en charge.", "AVG(created_at -> first in_progress|assigned event) / 60", "request.created_at, workflow_detail.created_at", "moyenne pondérée traçable"),
    _decision_kpi("avg_treatment_hours", "Délai moyen de traitement effectif.", "AVG(first in_progress|assigned event -> resolved_at) / 60", "workflow_detail.created_at, request.resolved_at", "moyenne pondérée traçable"),
    _decision_kpi("avg_resolution_hours", "Délai moyen de résolution.", "AVG(created_at -> resolved_at) / 60", "request.created_at, request.resolved_at", "moyenne pondérée"),
    _decision_kpi("avg_closure_hours", "Délai moyen de fermeture après résolution.", "AVG(resolved_at -> closed_at) / 60", "request.resolved_at, request.closed_at", "moyenne pondérée"),
    _decision_kpi("avg_ticket_age_hours", "Ancienneté moyenne des tickets.", "AVG(created_at -> closed_at|resolved_at|NOW)", "request.created_at, request.resolved_at, request.closed_at", "moyenne pondérée"),
    _decision_kpi("oldest_active_ticket_hours", "Ancienneté du plus vieux ticket actif.", "MAX(created_at -> NOW) pour statuts actifs", "request.created_at, request_status.code", "maximum"),
    _decision_kpi("unassigned_tickets", "Tickets sans affectation.", "assignee_id IS NULL", "request.assignee_id", "somme"),
    _decision_kpi("inactive_tickets", "Tickets actifs sans activité récente.", "active status AND last_activity_age_hours >= inactive_days * 24", "workflow_detail.created_at, request.updated_at", "somme"),
    _decision_kpi("internal_tickets", "Tickets d'origine interne.", "is_external = false", "request.is_external", "somme"),
    _decision_kpi("external_tickets", "Tickets d'origine externe.", "is_external = true", "request.is_external", "somme"),
    _decision_kpi("comment_count", "Volume de commentaires.", "COUNT(workflow_detail WHERE event_type = comment_added)", "workflow_detail.event_type", "somme"),
    _decision_kpi("interaction_count", "Volume total d'interactions tracées.", "COUNT(workflow_detail.id)", "workflow_detail.id", "somme"),
    _decision_kpi("attachment_count", "Nombre de pièces jointes.", "COUNT(attachment.id)", "attachment.request_id", "somme"),
    _decision_kpi("avg_satisfaction_rating", "Satisfaction moyenne lorsque notée.", "AVG(appreciation.rating)", "appreciation.rating", "moyenne pondérée"),
    _decision_kpi("dominant_priority", "Priorité la plus fréquente.", "MODE(priority)", "priority_definition.slug", "recalcul par groupe"),
    _decision_kpi("dominant_category", "Catégorie la plus fréquente.", "MODE(category)", "request_category.code", "recalcul par groupe"),
    _decision_kpi("dominant_source", "Canal de soumission le plus fréquent.", "MODE(request_source)", "request.request_source", "recalcul par groupe"),
    _decision_kpi("trend_total_delta", "Évolution du volume versus période précédente.", "current_total - previous_total", "KPI période courante et précédente", "recalcul par groupe"),
    _decision_kpi("trend_total_delta_pct", "Évolution en pourcentage versus période précédente.", "(current_total - previous_total) / previous_total * 100", "KPI période courante et précédente", "recalcul par groupe"),
]


class ReportService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def _scoped_unity_ids(self, unity_id: int) -> list[int]:
        """Retourne l'unité demandée si ce n'est pas une direction, puis tous ses descendants."""
        root_result = await self.session.execute(
            select(Organigram.id, Organigram.unity_id, Unity.label)
            .join(Unity, Unity.id == Organigram.unity_id)
            .where(Organigram.unity_id == unity_id)
            .where(Organigram.deleted_at.is_(None))
            .where(Unity.deleted_at.is_(None))
            .limit(1)
        )
        root = root_result.first()
        if root is None:
            return [int(unity_id)]

        ids: list[int] = []
        root_label = (root.label or "").strip().lower()
        if not root_label.startswith("direction "):
            ids.append(int(root.unity_id))

        pending_parent_ids = [int(root.id)]
        seen_parent_ids: set[int] = set()
        while pending_parent_ids:
            parent_id = pending_parent_ids.pop(0)
            if parent_id in seen_parent_ids:
                continue
            seen_parent_ids.add(parent_id)

            children_result = await self.session.execute(
                select(Organigram.id, Organigram.unity_id, Unity.label)
                .join(Unity, Unity.id == Organigram.unity_id)
                .where(Organigram.parent_id == parent_id)
                .where(Organigram.deleted_at.is_(None))
                .where(Unity.deleted_at.is_(None))
                .order_by(Organigram.id)
            )
            for child in children_result.all():
                child_label = (child.label or "").strip().lower()
                if not child_label.startswith("direction "):
                    ids.append(int(child.unity_id))
                pending_parent_ids.append(int(child.id))

        return sorted(set(ids))

    # ── Moteur décisionnel ───────────────────────────────────────────────────

    def _decision_period(
        self,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> tuple[date, date, date, date]:
        end = end_date or date.today()
        start = start_date or (end - timedelta(days=30))
        if start > end:
            start, end = end, start
        span_days = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=span_days - 1)
        return start, end, previous_start, previous_end

    def _decision_conditions(
        self,
        start: date,
        end: date,
        *,
        direction_id: Optional[int] = None,
        unity_id: Optional[int] | list[int] = None,
        assignee_id: Optional[int] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        source: Optional[str] = None,
        origin: Optional[str] = None,
        search: Optional[str] = None,
    ) -> tuple[str, dict[str, Any]]:
        conditions = [
            "r.deleted_at IS NULL",
            "DATE(r.created_at) BETWEEN :start AND :end",
        ]
        params: dict[str, Any] = {"start": start.isoformat(), "end": end.isoformat()}

        def add_csv_filter(column: str, raw_value: Optional[str], prefix: str) -> None:
            if not raw_value:
                return
            values = [value.strip() for value in raw_value.split(",") if value.strip()]
            if not values:
                return
            placeholders = []
            for index, value in enumerate(values):
                param_name = f"{prefix}_{index}"
                placeholders.append(f":{param_name}")
                params[param_name] = value
            conditions.append(f"{column} IN ({', '.join(placeholders)})")

        if direction_id is not None:
            conditions.append("(u.id = :direction_id OR u.parent_direction_id = :direction_id)")
            params["direction_id"] = int(direction_id)
        if unity_id is not None:
            if isinstance(unity_id, (list, set, tuple)):
                ids = [int(v) for v in unity_id] or [-1]
                placeholders = [f":unity_id_{i}" for i in range(len(ids))]
                params.update({f"unity_id_{i}": v for i, v in enumerate(ids)})
                conditions.append(f"r.unity_id IN ({', '.join(placeholders)})")
            else:
                conditions.append("r.unity_id = :unity_id")
                params["unity_id"] = int(unity_id)
        if assignee_id is not None:
            conditions.append("r.assignee_id = :assignee_id")
            params["assignee_id"] = int(assignee_id)
        add_csv_filter("rs.code", status, "status")
        add_csv_filter("rc.code", category, "category")
        add_csv_filter("pd.slug", priority, "priority")
        add_csv_filter("r.request_source", source, "source")
        if origin == "internal":
            conditions.append("r.is_external = 0")
        elif origin == "external":
            conditions.append("r.is_external = 1")
        if search:
            params["search"] = f"%{search.strip()}%"
            conditions.append(
                "(r.ref LIKE :search OR r.title LIKE :search OR r.requester_name LIKE :search "
                "OR COALESCE(u.label, '') LIKE :search OR COALESCE(a.name, '') LIKE :search)"
            )
        return " AND ".join(conditions), params

    async def _decision_rows(
        self,
        start: date,
        end: date,
        *,
        direction_id: Optional[int] = None,
        unity_id: Optional[int] | list[int] = None,
        assignee_id: Optional[int] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        source: Optional[str] = None,
        origin: Optional[str] = None,
        search: Optional[str] = None,
        inactive_days: int = DEFAULT_INACTIVE_DAYS,
    ) -> list[dict[str, Any]]:
        conditions, params = self._decision_conditions(
            start,
            end,
            direction_id=direction_id,
            unity_id=unity_id,
            assignee_id=assignee_id,
            status=status,
            category=category,
            priority=priority,
            source=source,
            origin=origin,
            search=search,
        )
        params["inactive_hours"] = max(int(inactive_days or DEFAULT_INACTIVE_DAYS), 0) * 24
        result = await self.session.execute(
            text(f"""
                SELECT
                    r.id AS ticket_id,
                    r.uuid AS ticket_uuid,
                    r.ref AS ticket_ref,
                    r.title AS ticket_title,
                    r.description AS ticket_description,
                    r.created_at,
                    r.updated_at,
                    r.resolved_at,
                    r.closed_at,
                    r.request_source,
                    r.requester_name,
                    r.requester_type,
                    r.is_external,
                    r.location_label,
                    r.lat,
                    r.lng,
                    rs.code AS status_code,
                    pd.slug AS priority_code,
                    rc.code AS category_code,
                    r.sla_hours,
                    r.sla_elapsed,
                    r.sla_breached,
                    r.in_triage,
                    COALESCE(u.parent_direction_id, u.id) AS direction_id,
                    COALESCE(du.label, CASE WHEN u.parent_direction_id IS NULL THEN u.label END, 'Non rattaché') AS direction_label,
                    CASE WHEN u.parent_direction_id IS NULL THEN NULL ELSE u.id END AS unity_id,
                    CASE WHEN u.parent_direction_id IS NULL THEN 'Sans service' ELSE u.label END AS unity_label,
                    u.codename AS unity_codename,
                    a.id AS assignee_id,
                    COALESCE(a.name, 'Non assigné') AS assignee_name,
                    a.role AS assignee_role,
                    DATE(r.created_at) AS period_day,
                    DATE_FORMAT(r.created_at, '%Y-%m') AS period_month,
                    COALESCE(evt.escalation_events, 0) AS escalation_events,
                    COALESCE(evt.reopen_events, 0) AS reopen_events,
                    COALESCE(evt.comment_count, 0) AS comment_count,
                    COALESCE(evt.interaction_count, 0) AS interaction_count,
                    COALESCE(att.attachment_count, 0) AS attachment_count,
                    evt.escalation_reasons,
                    evt.reopen_reasons,
                    COALESCE(evt.last_activity_at, r.updated_at, r.created_at) AS last_activity_at,
                    TIMESTAMPDIFF(HOUR, COALESCE(evt.last_activity_at, r.updated_at, r.created_at), NOW()) AS last_activity_age_hours,
                    CASE WHEN rs.code IN ('new','qualifying','qualified','assigned','in_progress','pending','escalated','reopened')
                          AND TIMESTAMPDIFF(HOUR, COALESCE(evt.last_activity_at, r.updated_at, r.created_at), NOW()) >= :inactive_hours
                         THEN 1 ELSE 0
                    END AS is_inactive,
                    ap.rating AS satisfaction_rating,
                    ap.resolved_confirmed AS satisfaction_confirmed,
                    CASE WHEN evt.qualification_at IS NOT NULL
                         THEN TIMESTAMPDIFF(MINUTE, r.created_at, evt.qualification_at)
                    END AS qualification_minutes,
                    CASE WHEN evt.assignment_at IS NOT NULL
                         THEN TIMESTAMPDIFF(MINUTE, r.created_at, evt.assignment_at)
                    END AS assignment_minutes,
                    CASE WHEN COALESCE(evt.treatment_started_at, evt.assignment_at) IS NOT NULL
                         THEN TIMESTAMPDIFF(MINUTE, r.created_at, COALESCE(evt.treatment_started_at, evt.assignment_at))
                    END AS first_response_minutes,
                    CASE WHEN COALESCE(evt.treatment_started_at, evt.assignment_at) IS NOT NULL
                          AND COALESCE(r.resolved_at, evt.resolved_event_at) IS NOT NULL
                         THEN TIMESTAMPDIFF(
                            MINUTE,
                            COALESCE(evt.treatment_started_at, evt.assignment_at),
                            COALESCE(r.resolved_at, evt.resolved_event_at)
                         )
                    END AS treatment_minutes,
                    CASE WHEN COALESCE(r.resolved_at, evt.resolved_event_at) IS NOT NULL
                         THEN TIMESTAMPDIFF(MINUTE, r.created_at, COALESCE(r.resolved_at, evt.resolved_event_at))
                    END AS resolution_minutes,
                    CASE WHEN COALESCE(r.resolved_at, evt.resolved_event_at) IS NOT NULL
                          AND COALESCE(r.closed_at, evt.closed_event_at) IS NOT NULL
                         THEN TIMESTAMPDIFF(
                            MINUTE,
                            COALESCE(r.resolved_at, evt.resolved_event_at),
                            COALESCE(r.closed_at, evt.closed_event_at)
                         )
                    END AS closure_minutes,
                    TIMESTAMPDIFF(HOUR, r.created_at, COALESCE(r.closed_at, r.resolved_at, NOW())) AS ticket_age_hours,
                    CASE WHEN rs.code IN ('new','qualifying','qualified','assigned','in_progress','pending','escalated','reopened')
                         THEN TIMESTAMPDIFF(HOUR, r.created_at, NOW())
                    END AS active_age_hours
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                JOIN priority_definition pd ON pd.id = r.priority_definition_id
                JOIN request_category rc ON rc.id = r.request_category_id
                LEFT JOIN unity u ON u.id = r.unity_id AND u.deleted_at IS NULL
                LEFT JOIN unity du ON du.id = u.parent_direction_id AND du.deleted_at IS NULL
                LEFT JOIN account a ON a.id = r.assignee_id AND a.deleted_at IS NULL
                LEFT JOIN (
                    SELECT
                        w.request_id,
                        MIN(CASE WHEN wd.event_type IN ('qualifying','qualified','assigned')
                                 THEN wd.created_at END) AS qualification_at,
                        MIN(CASE WHEN wd.event_type IN ('assigned','reassigned_service')
                                 THEN wd.created_at END) AS assignment_at,
                        MIN(CASE WHEN wd.event_type = 'in_progress'
                                 THEN wd.created_at END) AS treatment_started_at,
                        MIN(CASE WHEN wd.event_type = 'resolved'
                                 THEN wd.created_at END) AS resolved_event_at,
                        MIN(CASE WHEN wd.event_type = 'closed'
                                 THEN wd.created_at END) AS closed_event_at,
                        SUM(CASE WHEN wd.event_type IN ('escalated','escalation_manual')
                                 THEN 1 ELSE 0 END) AS escalation_events,
                        SUM(CASE WHEN wd.event_type = 'reopened'
                                 THEN 1 ELSE 0 END) AS reopen_events,
                        SUM(CASE WHEN wd.event_type = 'comment_added'
                                 THEN 1 ELSE 0 END) AS comment_count,
                        COUNT(wd.id) AS interaction_count,
                        MAX(wd.created_at) AS last_activity_at,
                        GROUP_CONCAT(
                            CASE WHEN wd.event_type IN ('escalated','escalation_manual')
                                 THEN COALESCE(wd.comment, wd.label)
                            END SEPARATOR ' | '
                        ) AS escalation_reasons,
                        GROUP_CONCAT(
                            CASE WHEN wd.event_type IN ('reopened','reopen_requested')
                                 THEN COALESCE(wd.comment, wd.label)
                            END SEPARATOR ' | '
                        ) AS reopen_reasons
                    FROM workflow_detail wd
                    JOIN workflow w ON w.id = wd.workflow_id AND w.deleted_at IS NULL
                    JOIN request rf ON rf.id = w.request_id AND rf.deleted_at IS NULL
                        AND DATE(rf.created_at) BETWEEN :start AND :end
                    WHERE wd.deleted_at IS NULL
                    GROUP BY w.request_id
                ) evt ON evt.request_id = r.id
                LEFT JOIN (
                    SELECT att.request_id, COUNT(*) AS attachment_count
                    FROM attachment att
                    JOIN request rf2 ON rf2.id = att.request_id AND rf2.deleted_at IS NULL
                        AND DATE(rf2.created_at) BETWEEN :start AND :end
                    WHERE att.deleted_at IS NULL
                    GROUP BY att.request_id
                ) att ON att.request_id = r.id
                LEFT JOIN appreciation ap ON ap.request_id = r.id AND ap.deleted_at IS NULL
                WHERE {conditions}
                ORDER BY r.created_at DESC
            """),
            params,
        )
        return [dict(r) for r in result.mappings().all()]

    def _metric_seed(self) -> dict[str, Any]:
        return {
            "total_tickets": 0,
            "new_tickets": 0,
            "qualifying_tickets": 0,
            "assigned_tickets": 0,
            "open_tickets": 0,
            "closed_tickets": 0,
            "resolved_tickets": 0,
            "in_progress_tickets": 0,
            "pending_tickets": 0,
            "pending_validation_tickets": 0,
            "escalated_tickets": 0,
            "reopened_tickets": 0,
            "backlog_tickets": 0,
            "critical_tickets": 0,
            "urgent_tickets": 0,
            "overdue_tickets": 0,
            "sla_breached_tickets": 0,
            "sla_respected_tickets": 0,
            "unassigned_tickets": 0,
            "internal_tickets": 0,
            "external_tickets": 0,
            "inactive_tickets": 0,
            "comment_count": 0,
            "interaction_count": 0,
            "attachment_count": 0,
            "oldest_active_ticket_hours": 0,
            "_duration_minutes": {
                "qualification": 0.0,
                "assignment": 0.0,
                "first_response": 0.0,
                "treatment": 0.0,
                "resolution": 0.0,
                "closure": 0.0,
            },
            "_duration_counts": {
                "qualification": 0,
                "assignment": 0,
                "first_response": 0,
                "treatment": 0,
                "resolution": 0,
                "closure": 0,
            },
            "_age_hours_total": 0.0,
            "_age_count": 0,
            "_rating_total": 0.0,
            "_rating_count": 0,
            "_status_counts": {},
            "_priority_counts": {},
            "_category_counts": {},
            "_source_counts": {},
        }

    def _add_minutes(self, metrics: dict[str, Any], key: str, value: Any) -> None:
        if value is None:
            return
        minutes = float(value)
        if minutes < 0:
            return
        metrics["_duration_minutes"][key] += minutes
        metrics["_duration_counts"][key] += 1

    def _inc_bucket(self, metrics: dict[str, Any], bucket: str, value: Any) -> None:
        normalized = str(value or "Non renseigné")
        metrics[bucket][normalized] = metrics[bucket].get(normalized, 0) + 1

    def _add_row_to_metrics(self, metrics: dict[str, Any], row: dict[str, Any]) -> None:
        status_code = str(row.get("status_code") or "")
        priority_code = str(row.get("priority_code") or "")
        category_code = str(row.get("category_code") or "")
        source_code = str(row.get("request_source") or "Non renseigné")
        escalation_events = int(row.get("escalation_events") or 0)
        reopen_events = int(row.get("reopen_events") or 0)
        sla_hours = int(row.get("sla_hours") or 0)
        sla_breached = bool(row.get("sla_breached"))

        metrics["total_tickets"] += 1
        self._inc_bucket(metrics, "_status_counts", status_code)
        self._inc_bucket(metrics, "_priority_counts", priority_code)
        self._inc_bucket(metrics, "_category_counts", category_code)
        self._inc_bucket(metrics, "_source_counts", source_code)
        if status_code == "new":
            metrics["new_tickets"] += 1
        if bool(row.get("in_triage")) or status_code == "qualifying":
            metrics["qualifying_tickets"] += 1
        if status_code == "assigned":
            metrics["assigned_tickets"] += 1
        if status_code in ACTIVE_STATUS_CODES:
            metrics["open_tickets"] += 1
        if status_code in BACKLOG_STATUS_CODES:
            metrics["backlog_tickets"] += 1
        if status_code == "closed":
            metrics["closed_tickets"] += 1
        if status_code == "resolved":
            metrics["resolved_tickets"] += 1
        if status_code == "in_progress":
            metrics["in_progress_tickets"] += 1
        if status_code in {"pending", "pending_validation"}:
            metrics["pending_tickets"] += 1
            metrics["pending_validation_tickets"] += 1
        if status_code == "escalated" or escalation_events > 0:
            metrics["escalated_tickets"] += 1
        if status_code == "reopened" or reopen_events > 0:
            metrics["reopened_tickets"] += 1
        if priority_code == "critical":
            metrics["critical_tickets"] += 1
        if priority_code in URGENT_PRIORITY_CODES:
            metrics["urgent_tickets"] += 1
        if sla_breached:
            metrics["overdue_tickets"] += 1
            metrics["sla_breached_tickets"] += 1
        elif sla_hours > 0:
            metrics["sla_respected_tickets"] += 1
        if row.get("assignee_id") is None:
            metrics["unassigned_tickets"] += 1
        if bool(row.get("is_external")):
            metrics["external_tickets"] += 1
        else:
            metrics["internal_tickets"] += 1
        if int(row.get("is_inactive") or 0) == 1:
            metrics["inactive_tickets"] += 1
        metrics["comment_count"] += int(row.get("comment_count") or 0)
        metrics["interaction_count"] += int(row.get("interaction_count") or 0)
        metrics["attachment_count"] += int(row.get("attachment_count") or 0)

        self._add_minutes(metrics, "qualification", row.get("qualification_minutes"))
        self._add_minutes(metrics, "assignment", row.get("assignment_minutes"))
        self._add_minutes(metrics, "first_response", row.get("first_response_minutes"))
        self._add_minutes(metrics, "treatment", row.get("treatment_minutes"))
        self._add_minutes(metrics, "resolution", row.get("resolution_minutes"))
        self._add_minutes(metrics, "closure", row.get("closure_minutes"))

        rating = row.get("satisfaction_rating")
        if rating is not None:
            metrics["_rating_total"] += float(rating)
            metrics["_rating_count"] += 1
        age_hours = row.get("ticket_age_hours")
        if age_hours is not None:
            metrics["_age_hours_total"] += float(age_hours)
            metrics["_age_count"] += 1
        active_age = row.get("active_age_hours")
        if active_age is not None:
            metrics["oldest_active_ticket_hours"] = max(
                int(metrics["oldest_active_ticket_hours"]),
                int(active_age),
            )

    def _finalize_metrics(self, metrics: dict[str, Any]) -> dict[str, Any]:
        total = int(metrics["total_tickets"])
        finished = int(metrics["resolved_tickets"]) + int(metrics["closed_tickets"])
        result = {k: v for k, v in metrics.items() if not k.startswith("_")}
        result["resolution_rate"] = round(finished * 100.0 / total, 1) if total else 0.0
        result["closure_rate"] = round(int(metrics["closed_tickets"]) * 100.0 / total, 1) if total else 0.0
        sla_total = int(metrics["sla_respected_tickets"]) + int(metrics["sla_breached_tickets"])
        result["sla_compliance_rate"] = (
            round(int(metrics["sla_respected_tickets"]) * 100.0 / sla_total, 1)
            if sla_total
            else 100.0
        )

        for key in ("qualification", "assignment", "first_response", "treatment", "resolution", "closure"):
            count = metrics["_duration_counts"][key]
            minutes = metrics["_duration_minutes"][key]
            result[f"avg_{key}_hours"] = round((minutes / count) / 60.0, 1) if count else None

        age_count = metrics["_age_count"]
        result["avg_ticket_age_hours"] = round(metrics["_age_hours_total"] / age_count, 1) if age_count else None
        rating_count = metrics["_rating_count"]
        result["avg_satisfaction_rating"] = (
            round(metrics["_rating_total"] / rating_count, 2)
            if rating_count
            else None
        )

        def dominant(bucket: dict[str, int]) -> str | None:
            if not bucket:
                return None
            return max(bucket.items(), key=lambda item: item[1])[0]

        result["dominant_status"] = dominant(metrics["_status_counts"])
        result["dominant_priority"] = dominant(metrics["_priority_counts"])
        result["dominant_category"] = dominant(metrics["_category_counts"])
        result["dominant_source"] = dominant(metrics["_source_counts"])
        return result

    def _aggregate_rows(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        metrics = self._metric_seed()
        for row in rows:
            self._add_row_to_metrics(metrics, row)
        return self._finalize_metrics(metrics)

    def _breakdown(
        self,
        rows: list[dict[str, Any]],
        *,
        level: str,
        id_key: str,
        label_key: str,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            raw_id = row.get(id_key)
            group_id = str(raw_id if raw_id is not None else "none")
            if group_id not in grouped:
                grouped[group_id] = {
                    "id": group_id,
                    "label": row.get(label_key) or "Non renseigné",
                    "level": level,
                    "_metrics": self._metric_seed(),
                }
            self._add_row_to_metrics(grouped[group_id]["_metrics"], row)

        result = []
        for item in grouped.values():
            result.append({
                "id": item["id"],
                "label": item["label"],
                "level": item["level"],
                "metrics": self._finalize_metrics(item["_metrics"]),
            })
        return sorted(result, key=lambda x: x["metrics"]["total_tickets"], reverse=True)

    def _period_breakdown(
        self,
        rows: list[dict[str, Any]],
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        period_key = "period_month" if (end - start).days > 62 else "period_day"
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            period_value = row.get(period_key)
            group_id = str(period_value)
            if group_id not in grouped:
                grouped[group_id] = {
                    "id": group_id,
                    "label": group_id,
                    "level": "period",
                    "_metrics": self._metric_seed(),
                }
            self._add_row_to_metrics(grouped[group_id]["_metrics"], row)
        return [
            {
                "id": item["id"],
                "label": item["label"],
                "level": item["level"],
                "metrics": self._finalize_metrics(item["_metrics"]),
            }
            for item in sorted(grouped.values(), key=lambda x: x["id"])
        ]

    def _group_key(self, row: dict[str, Any], group_by: str, start: date, end: date) -> tuple[Any, ...]:
        if group_by in {"global", "executive"}:
            return ("global",)
        if group_by == "direction":
            return (row.get("direction_id") or "none",)
        if group_by == "service":
            return (row.get("direction_id") or "none", row.get("unity_id") or "none")
        if group_by == "status":
            return (row.get("status_code") or "none",)
        if group_by == "category":
            return (row.get("category_code") or "none",)
        if group_by == "priority":
            return (row.get("priority_code") or "none",)
        if group_by == "assignee":
            return (
                row.get("direction_id") or "none",
                row.get("unity_id") or "none",
                row.get("assignee_id") or "unassigned",
            )
        if group_by == "period":
            period_key = "period_month" if (end - start).days > 62 else "period_day"
            return (row.get(period_key) or "none",)
        return (row.get("direction_id") or "none",)

    def _dimension_values(self, row: dict[str, Any], group_by: str, key: tuple[Any, ...]) -> dict[str, Any]:
        values = {
            "direction": row.get("direction_label") or "Non rattaché",
            "service_unity": row.get("unity_label") or "Sans service",
            "responsable_traitement": row.get("assignee_name") or "Non assigné",
            "agent_role": row.get("assignee_role"),
            "status": row.get("status_code"),
            "category": row.get("category_code"),
            "priority": row.get("priority_code"),
            "submission_channel": row.get("request_source") or "Non renseigné",
            "origin": "Externe" if row.get("is_external") else "Interne",
            "period": None,
        }
        if group_by == "global":
            values["direction"] = "EDG"
            values["service_unity"] = "Toutes unités"
            values["responsable_traitement"] = "Tous"
        elif group_by == "direction":
            values["service_unity"] = "Tous services"
            values["responsable_traitement"] = "Tous"
        elif group_by == "status":
            values["direction"] = "Toutes directions"
            values["service_unity"] = "Tous services"
            values["status"] = str(key[0])
        elif group_by == "category":
            values["direction"] = "Toutes directions"
            values["service_unity"] = "Tous services"
            values["category"] = str(key[0])
        elif group_by == "priority":
            values["direction"] = "Toutes directions"
            values["service_unity"] = "Tous services"
            values["priority"] = str(key[0])
        elif group_by == "period":
            values["direction"] = "Toutes directions"
            values["service_unity"] = "Tous services"
            values["period"] = str(key[0])
        return values

    def _table_row(
        self,
        key: tuple[Any, ...],
        rows: list[dict[str, Any]],
        previous_rows: list[dict[str, Any]],
        group_by: str,
    ) -> dict[str, Any]:
        first = rows[0] if rows else {}
        metrics = self._aggregate_rows(rows)
        previous_metrics = self._aggregate_rows(previous_rows)
        dimensions = self._dimension_values(first, group_by, key)
        total_trend = self._trend_value(
            float(metrics.get("total_tickets") or 0),
            float(previous_metrics.get("total_tickets") or 0),
        )
        oldest_active_dates = [
            row.get("created_at")
            for row in rows
            if row.get("active_age_hours") is not None and row.get("created_at") is not None
        ]
        last_activities = [
            row.get("last_activity_at")
            for row in rows
            if row.get("last_activity_at") is not None
        ]
        return {
            "group_key": "|".join(str(part) for part in key),
            "group_by": group_by,
            **dimensions,
            "total_tickets": metrics.get("total_tickets"),
            "new_tickets": metrics.get("new_tickets"),
            "qualifying_tickets": metrics.get("qualifying_tickets"),
            "assigned_tickets": metrics.get("assigned_tickets"),
            "in_progress_tickets": metrics.get("in_progress_tickets"),
            "pending_validation_tickets": metrics.get("pending_validation_tickets"),
            "resolved_tickets": metrics.get("resolved_tickets"),
            "closed_tickets": metrics.get("closed_tickets"),
            "escalated_tickets": metrics.get("escalated_tickets"),
            "reopened_tickets": metrics.get("reopened_tickets"),
            "overdue_tickets": metrics.get("overdue_tickets"),
            "sla_respected_tickets": metrics.get("sla_respected_tickets"),
            "sla_breached_tickets": metrics.get("sla_breached_tickets"),
            "sla_compliance_rate": metrics.get("sla_compliance_rate"),
            "resolution_rate": metrics.get("resolution_rate"),
            "closure_rate": metrics.get("closure_rate"),
            "backlog_tickets": metrics.get("backlog_tickets"),
            "avg_ticket_age_hours": metrics.get("avg_ticket_age_hours"),
            "avg_qualification_hours": metrics.get("avg_qualification_hours"),
            "avg_assignment_hours": metrics.get("avg_assignment_hours"),
            "avg_first_response_hours": metrics.get("avg_first_response_hours"),
            "avg_treatment_hours": metrics.get("avg_treatment_hours"),
            "avg_resolution_hours": metrics.get("avg_resolution_hours"),
            "avg_closure_hours": metrics.get("avg_closure_hours"),
            "dominant_priority": metrics.get("dominant_priority"),
            "dominant_category": metrics.get("dominant_category"),
            "critical_tickets": metrics.get("critical_tickets"),
            "urgent_tickets": metrics.get("urgent_tickets"),
            "unassigned_tickets": metrics.get("unassigned_tickets"),
            "internal_tickets": metrics.get("internal_tickets"),
            "external_tickets": metrics.get("external_tickets"),
            "inactive_tickets": metrics.get("inactive_tickets"),
            "comment_count": metrics.get("comment_count"),
            "interaction_count": metrics.get("interaction_count"),
            "attachment_count": metrics.get("attachment_count"),
            "avg_satisfaction_rating": metrics.get("avg_satisfaction_rating"),
            "oldest_active_ticket_hours": metrics.get("oldest_active_ticket_hours"),
            "oldest_active_ticket_date": min(oldest_active_dates).isoformat() if oldest_active_dates else None,
            "last_activity_at": max(last_activities).isoformat() if last_activities else None,
            "trend_total_delta": total_trend["delta"],
            "trend_total_delta_pct": total_trend["delta_pct"],
        }

    def _table_rows(
        self,
        rows: list[dict[str, Any]],
        previous_rows: list[dict[str, Any]],
        *,
        group_by: str,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        previous_grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(self._group_key(row, group_by, start, end), []).append(row)
        for row in previous_rows:
            previous_grouped.setdefault(self._group_key(row, group_by, start, end), []).append(row)

        result = [
            self._table_row(key, group_rows, previous_grouped.get(key, []), group_by)
            for key, group_rows in grouped.items()
        ]
        if group_by == "period":
            return sorted(result, key=lambda item: item.get("period") or "")
        return sorted(result, key=lambda item: int(item.get("total_tickets") or 0), reverse=True)

    def _audit_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "ticket_id": str(row.get("ticket_id")),
            "ticket_uuid": row.get("ticket_uuid"),
            "reference": row.get("ticket_ref"),
            "title": row.get("ticket_title"),
            "direction": row.get("direction_label") or "Non rattaché",
            "service_unity": row.get("unity_label") or "Sans service",
            "responsable_traitement": row.get("assignee_name") or "Non assigné",
            "agent_role": row.get("assignee_role"),
            "status": row.get("status_code"),
            "priority": row.get("priority_code"),
            "category": row.get("category_code"),
            "submission_channel": row.get("request_source") or "Non renseigné",
            "origin": "Externe" if row.get("is_external") else "Interne",
            "requester_name": row.get("requester_name"),
            "location_label": row.get("location_label"),
            "lat": row.get("lat"),
            "lng": row.get("lng"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "resolved_at": row.get("resolved_at"),
            "closed_at": row.get("closed_at"),
            "last_activity_at": row.get("last_activity_at"),
            "last_activity_age_hours": row.get("last_activity_age_hours"),
            "is_inactive": bool(row.get("is_inactive")),
            "sla_hours": row.get("sla_hours"),
            "sla_elapsed": row.get("sla_elapsed"),
            "sla_breached": bool(row.get("sla_breached")),
            "late_cause": "SLA dépassé" if row.get("sla_breached") else None,
            "qualification_hours": self._hours(row.get("qualification_minutes")),
            "assignment_hours": self._hours(row.get("assignment_minutes")),
            "first_response_hours": self._hours(row.get("first_response_minutes")),
            "treatment_hours": self._hours(row.get("treatment_minutes")),
            "resolution_hours": self._hours(row.get("resolution_minutes")),
            "closure_hours": self._hours(row.get("closure_minutes")),
            "ticket_age_hours": row.get("ticket_age_hours"),
            "active_age_hours": row.get("active_age_hours"),
            "escalation_count": row.get("escalation_events"),
            "escalation_reasons": row.get("escalation_reasons"),
            "reopen_count": row.get("reopen_events"),
            "reopen_reasons": row.get("reopen_reasons"),
            "comment_count": row.get("comment_count"),
            "interaction_count": row.get("interaction_count"),
            "attachment_count": row.get("attachment_count"),
            "satisfaction_rating": row.get("satisfaction_rating"),
            "satisfaction_confirmed": row.get("satisfaction_confirmed"),
        }

    def _hours(self, minutes: Any) -> float | None:
        if minutes is None:
            return None
        return round(float(minutes) / 60.0, 1)

    def _sort_tabular_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        sort_by: str = "total_tickets",
        sort_dir: str = "desc",
    ) -> list[dict[str, Any]]:
        reverse = sort_dir.lower() != "asc"

        def normalize(value: Any) -> Any:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            return str(value).lower()

        filled_rows = [item for item in rows if item.get(sort_by) is not None]
        empty_rows = [item for item in rows if item.get(sort_by) is None]
        return sorted(filled_rows, key=lambda item: normalize(item.get(sort_by)), reverse=reverse) + empty_rows

    def _paginate_rows(self, rows: list[dict[str, Any]], *, page: int, limit: int) -> dict[str, Any]:
        safe_page = max(int(page or 1), 1)
        safe_limit = min(max(int(limit or 50), 1), 500)
        total = len(rows)
        start_index = (safe_page - 1) * safe_limit
        page_rows = rows[start_index:start_index + safe_limit]
        pages = (total + safe_limit - 1) // safe_limit if total else 0
        return {
            "rows": page_rows,
            "pagination": {
                "page": safe_page,
                "limit": safe_limit,
                "total": total,
                "pages": pages,
            },
        }

    def _decision_column_groups(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "executive": [
                {"group": "Périmètre", "columns": ["direction", "service_unity"]},
                {"group": "Volumes", "columns": ["total_tickets", "open_tickets", "backlog_tickets", "critical_tickets"]},
                {"group": "SLA", "columns": ["sla_compliance_rate", "sla_breached_tickets", "overdue_tickets"]},
                {"group": "Performance", "columns": ["resolution_rate", "closure_rate", "avg_resolution_hours"]},
                {"group": "Tendance", "columns": ["trend_total_delta", "trend_total_delta_pct"]},
            ],
            "analytical": [
                {"group": "Périmètre", "columns": ["direction", "service_unity", "responsable_traitement"]},
                {"group": "Statuts", "columns": ["new_tickets", "qualifying_tickets", "assigned_tickets", "in_progress_tickets", "pending_validation_tickets", "resolved_tickets", "closed_tickets", "escalated_tickets", "reopened_tickets"]},
                {"group": "SLA", "columns": ["sla_respected_tickets", "sla_breached_tickets", "sla_compliance_rate", "oldest_active_ticket_date"]},
                {"group": "Délais", "columns": ["avg_qualification_hours", "avg_assignment_hours", "avg_first_response_hours", "avg_treatment_hours", "avg_resolution_hours", "avg_closure_hours"]},
                {"group": "Qualité", "columns": ["dominant_priority", "dominant_category", "avg_satisfaction_rating", "comment_count", "attachment_count"]},
            ],
            "audit": [
                {"group": "Ticket", "columns": ["reference", "title", "status", "priority", "category"]},
                {"group": "Organisation", "columns": ["direction", "service_unity", "responsable_traitement"]},
                {"group": "Origine", "columns": ["submission_channel", "origin", "requester_name", "location_label"]},
                {"group": "Dates", "columns": ["created_at", "last_activity_at", "resolved_at", "closed_at"]},
                {"group": "SLA et délais", "columns": ["sla_breached", "late_cause", "first_response_hours", "resolution_hours"]},
                {"group": "Traçabilité", "columns": ["escalation_reasons", "reopen_reasons", "comment_count", "interaction_count", "attachment_count"]},
            ],
        }

    def _ticket_leaf(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row.get("ticket_id")),
            "uuid": row.get("ticket_uuid"),
            "ref": row.get("ticket_ref"),
            "title": row.get("ticket_title"),
            "status": row.get("status_code"),
            "priority": row.get("priority_code"),
            "category": row.get("category_code"),
            "created_at": row.get("created_at"),
            "sla_breached": bool(row.get("sla_breached")),
        }

    def _build_hierarchy(
        self,
        rows: list[dict[str, Any]],
        *,
        include_tickets: bool = False,
    ) -> dict[str, Any]:
        root = {
            "id": "edg",
            "label": "EDG",
            "level": "edg",
            "_metrics": self._metric_seed(),
            "children": {},
        }

        for row in rows:
            self._add_row_to_metrics(root["_metrics"], row)
            direction_id = str(row.get("direction_id") or "none")
            direction = root["children"].setdefault(direction_id, {
                "id": direction_id,
                "label": row.get("direction_label") or "Non rattaché",
                "level": "direction",
                "_metrics": self._metric_seed(),
                "children": {},
            })
            self._add_row_to_metrics(direction["_metrics"], row)

            unity_id = str(row.get("unity_id") or f"direction-{direction_id}")
            unity = direction["children"].setdefault(unity_id, {
                "id": unity_id,
                "label": row.get("unity_label") or "Sans service",
                "level": "service",
                "_metrics": self._metric_seed(),
                "children": {},
            })
            self._add_row_to_metrics(unity["_metrics"], row)

            assignee_id = str(row.get("assignee_id") or "unassigned")
            assignee = unity["children"].setdefault(assignee_id, {
                "id": assignee_id,
                "label": row.get("assignee_name") or "Non assigné",
                "role": row.get("assignee_role"),
                "level": "agent",
                "_metrics": self._metric_seed(),
                "tickets": [],
            })
            self._add_row_to_metrics(assignee["_metrics"], row)
            if include_tickets:
                assignee["tickets"].append(self._ticket_leaf(row))

        def finalize_node(node: dict[str, Any]) -> dict[str, Any]:
            finalized = {
                "id": node["id"],
                "label": node["label"],
                "level": node["level"],
                "metrics": self._finalize_metrics(node["_metrics"]),
            }
            if "role" in node:
                finalized["role"] = node["role"]
            if "children" in node:
                finalized["children"] = [
                    finalize_node(child)
                    for child in sorted(
                        node["children"].values(),
                        key=lambda x: x["_metrics"]["total_tickets"],
                        reverse=True,
                    )
                ]
            if "tickets" in node:
                finalized["ticket_count"] = len(node["tickets"])
                if include_tickets:
                    finalized["tickets"] = node["tickets"]
            return finalized

        return finalize_node(root)

    def _trend_value(self, current: float, previous: float) -> dict[str, Any]:
        delta = current - previous
        if previous == 0:
            pct = 100.0 if current > 0 else 0.0
        else:
            pct = round(delta * 100.0 / previous, 1)
        return {"current": current, "previous": previous, "delta": delta, "delta_pct": pct}

    def _build_trends(
        self,
        current: dict[str, Any],
        previous: dict[str, Any],
    ) -> dict[str, Any]:
        keys = [
            "total_tickets",
            "open_tickets",
            "resolved_tickets",
            "closed_tickets",
            "backlog_tickets",
            "sla_breached_tickets",
        ]
        return {
            key: self._trend_value(float(current.get(key) or 0), float(previous.get(key) or 0))
            for key in keys
        }

    async def decision_report(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        *,
        direction_id: Optional[int] = None,
        unity_id: Optional[int] | list[int] = None,
        assignee_id: Optional[int] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        source: Optional[str] = None,
        origin: Optional[str] = None,
        search: Optional[str] = None,
        group_by: str = "service",
        inactive_days: int = DEFAULT_INACTIVE_DAYS,
        page: int = 1,
        limit: int = 50,
        sort_by: str = "total_tickets",
        sort_dir: str = "desc",
        include_tickets: bool = False,
        include_audit_rows: bool = False,
        generated_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Rapport décisionnel consolidé EDG → Direction → Service → Agent → Ticket.
        Chaque ticket est chargé une seule fois, puis agrégé aux niveaux supérieurs.
        """
        start, end, prev_start, prev_end = self._decision_period(start_date, end_date)
        group_by = group_by if group_by in DECISION_GROUPS else "service"
        rows = await self._decision_rows(
            start,
            end,
            direction_id=direction_id,
            unity_id=unity_id,
            assignee_id=assignee_id,
            status=status,
            category=category,
            priority=priority,
            source=source,
            origin=origin,
            search=search,
            inactive_days=inactive_days,
        )
        previous_rows = await self._decision_rows(
            prev_start,
            prev_end,
            direction_id=direction_id,
            unity_id=unity_id,
            assignee_id=assignee_id,
            status=status,
            category=category,
            priority=priority,
            source=source,
            origin=origin,
            search=search,
            inactive_days=inactive_days,
        )

        metrics = self._aggregate_rows(rows)
        previous_metrics = self._aggregate_rows(previous_rows)
        ticket_ids = [row["ticket_id"] for row in rows]
        unique_ticket_count = len(set(ticket_ids))
        executive_rows = self._table_rows(rows, previous_rows, group_by="direction", start=start, end=end)
        analytical_group = "service" if group_by in {"global", "executive", "audit"} else group_by
        analytical_rows = self._table_rows(rows, previous_rows, group_by=analytical_group, start=start, end=end)
        audit_rows = [self._audit_row(row) for row in rows]
        sorted_audit_rows = self._sort_tabular_rows(
            audit_rows,
            sort_by=sort_by if audit_rows and sort_by in audit_rows[0] else "created_at",
            sort_dir=sort_dir,
        )
        paginated_audit = self._paginate_rows(sorted_audit_rows, page=page, limit=limit)
        generated_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        filter_summary = {
            "direction_id": direction_id,
            "unity_id": unity_id,
            "assignee_id": assignee_id,
            "status": status,
            "category": category,
            "priority": priority,
            "source": source,
            "origin": origin,
            "search": search,
            "inactive_days": inactive_days,
        }

        return {
            "report_type": "decision",
            "generated_at": generated_at,
            "generated_by": generated_by,
            "period": {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "previous_start": prev_start.isoformat(),
                "previous_end": prev_end.isoformat(),
            },
            "filters": filter_summary,
            "kpis": metrics,
            "previous_kpis": previous_metrics,
            "trends": self._build_trends(metrics, previous_metrics),
            "hierarchy": self._build_hierarchy(rows, include_tickets=include_tickets),
            "tables": {
                "column_groups": self._decision_column_groups(),
                "capabilities": {
                    "sort": True,
                    "multi_filters": True,
                    "search": True,
                    "pagination": True,
                    "configurable_columns": True,
                    "grouping": ["direction", "service", "status", "category", "priority", "assignee", "period"],
                    "subtotals": True,
                    "grand_totals": True,
                    "export_full_scope": True,
                    "print_ready": True,
                },
                "executive": {
                    "level": "executive",
                    "group_by": "direction",
                    "rows": executive_rows,
                    "totals": metrics,
                },
                "analytical": {
                    "level": "analytical",
                    "group_by": analytical_group,
                    "rows": analytical_rows,
                    "totals": metrics,
                },
                "audit": {
                    "level": "audit",
                    "rows": paginated_audit["rows"],
                    "pagination": paginated_audit["pagination"],
                    "totals": metrics,
                    **({"export_rows": sorted_audit_rows} if include_audit_rows else {}),
                },
            },
            "breakdowns": {
                "direction": self._breakdown(rows, level="direction", id_key="direction_id", label_key="direction_label"),
                "service": self._breakdown(rows, level="service", id_key="unity_id", label_key="unity_label"),
                "status": self._breakdown(rows, level="status", id_key="status_code", label_key="status_code"),
                "category": self._breakdown(rows, level="category", id_key="category_code", label_key="category_code"),
                "priority": self._breakdown(rows, level="priority", id_key="priority_code", label_key="priority_code"),
                "assignee": self._breakdown(rows, level="assignee", id_key="assignee_id", label_key="assignee_name"),
                "period": self._period_breakdown(rows, start, end),
            },
            "kpi_catalog": DECISION_KPI_CATALOG,
            "data_quality": {
                "rows_loaded": len(rows),
                "unique_ticket_count": unique_ticket_count,
                "duplicate_ticket_count": len(rows) - unique_ticket_count,
                "historical_delay_source": "workflow_detail when event exists; otherwise metric is null",
                "missing_business_delay_cause": "Aucun champ structuré de cause de retard; late_cause est dérivé du SLA.",
            },
        }

    def decision_export_rows(self, report: dict[str, Any], group_by: str = "direction") -> list[dict[str, Any]]:
        filters = report.get("filters", {})
        period = report.get("period", {})
        metadata = {
            "periode": f"{period.get('start')} -> {period.get('end')}",
            "genere_le": report.get("generated_at"),
            "genere_par": report.get("generated_by"),
            "filtres": "; ".join(
                f"{key}={value}"
                for key, value in filters.items()
                if value not in (None, "")
            ) or "Aucun filtre",
        }

        if group_by == "audit":
            return [
                {**metadata, **row}
                for row in report.get("tables", {}).get("audit", {}).get("export_rows", report.get("tables", {}).get("audit", {}).get("rows", []))
            ]

        if group_by == "global":
            metrics = report["kpis"]
            source_rows = [{
                "group_key": "global",
                "group_by": "global",
                "direction": "EDG",
                "service_unity": "Toutes unités",
                "responsable_traitement": "Tous",
                **{key: value for key, value in metrics.items() if not isinstance(value, (dict, list))},
                "trend_total_delta": report.get("trends", {}).get("total_tickets", {}).get("delta"),
                "trend_total_delta_pct": report.get("trends", {}).get("total_tickets", {}).get("delta_pct"),
            }]
        elif group_by == "executive":
            source_rows = report.get("tables", {}).get("executive", {}).get("rows", [])
        else:
            source_rows = report.get("tables", {}).get("analytical", {}).get("rows", [])

        return [{**metadata, **row} for row in source_rows]

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
                    COALESCE(ROUND(
                        SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END)
                        * 100.0 / NULLIF(COUNT(r.id), 0), 1
                    ), 0) AS resolution_rate
                FROM account a
                LEFT JOIN unity u ON u.id = a.unity_id AND u.deleted_at IS NULL
                LEFT JOIN request r ON r.assignee_id = a.id AND {conditions}
                LEFT JOIN request_status rs ON rs.id = r.request_status_id
                WHERE a.deleted_at IS NULL AND a.role IN ('agent-support','chief-service','chief-departement')
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
        direction_id: Optional[int] = None,
        unity_id: Optional[int] = None,
    ) -> list[dict]:
        """
        Tickets par unité organisationnelle sur une période.
        """
        from datetime import date as dt_date
        today = dt_date.today()
        s = (start_date or (today - timedelta(days=30))).isoformat()
        e = (end_date or today).isoformat()
        params = {"start": s, "end": e}
        unity_scope = "AND u.parent_direction_id IS NOT NULL"
        stmt_params = None
        if unity_id is not None:
            unity_scope = "AND u.id = :unity_id"
            params["unity_id"] = int(unity_id)
        elif direction_id is not None:
            unity_ids = await self._scoped_unity_ids(int(direction_id))
            if not unity_ids:
                return []
            unity_scope = "AND u.id IN :unity_ids"
            params["unity_ids"] = unity_ids
            stmt_params = [bindparam("unity_ids", expanding=True)]

        stmt = text(f"""
                SELECT
                    u.id           AS unity_id,
                    u.label        AS unity_label,
                    u.codename     AS unity_codename,
                    COUNT(r.id)    AS total,
                    COUNT(r.id)    AS assigned_total,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')  THEN 1 ELSE 0 END) AS resolved,
                    SUM(CASE WHEN rs.code IN ('resolved','closed')  THEN 1 ELSE 0 END) AS resolved_total,
                    SUM(CASE WHEN rs.code = 'pending'               THEN 1 ELSE 0 END) AS pending_total,
                    SUM(CASE WHEN rs.code = 'escalated'             THEN 1 ELSE 0 END) AS escalated_total,
                    SUM(CASE WHEN rs.code IN ('new','qualifying','qualified',
                             'assigned','in_progress','escalated','reopened')
                                                                   THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN r.sla_breached = 1               THEN 1 ELSE 0 END) AS sla_breached,
                    ROUND(AVG(
                        CASE WHEN r.resolved_at IS NOT NULL
                             THEN TIMESTAMPDIFF(MINUTE, r.created_at, r.resolved_at) / 60
                        END
                    ), 1) AS avg_resolution_hours,
                    COALESCE(ROUND(
                        SUM(CASE WHEN rs.code IN ('resolved','closed') THEN 1 ELSE 0 END)
                        * 100.0 / NULLIF(COUNT(r.id), 0), 1
                    ), 0) AS resolution_rate
                FROM unity u
                LEFT JOIN request r
                    ON r.unity_id = u.id
                    AND r.deleted_at IS NULL
                    AND DATE(r.created_at) BETWEEN :start AND :end
                LEFT JOIN request_status rs ON rs.id = r.request_status_id
                WHERE u.deleted_at IS NULL
                  {unity_scope}
                  AND LOWER(u.label) NOT LIKE 'direction %'
                GROUP BY u.id, u.label, u.codename
                ORDER BY total DESC
            """)
        if stmt_params:
            stmt = stmt.bindparams(*stmt_params)

        result = await self.session.execute(
            stmt,
            params,
        )
        return [dict(r) for r in result.mappings().all()]

    # ── Centre SLA — tickets actifs en dépassement sur une période ────────────

    async def sla_center_breach_rows(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        direction_id: Optional[int] = None,
        unity_id: Optional[int] = None,
        group_by_direction: bool = False,
    ) -> list[dict]:
        """Tickets actifs en dépassement SLA créés sur la période, pour l'export
        du Centre SLA (mêmes règles que la page : statuts non terminaux + sla_breached)."""
        from datetime import date as dt_date
        today = dt_date.today()
        s = (start_date or (today - timedelta(days=30))).isoformat()
        e = (end_date or today).isoformat()
        params: dict = {"start": s, "end": e, "active_statuses": tuple(ACTIVE_STATUS_CODES)}
        stmt_params = [bindparam("active_statuses", expanding=True)]

        scope_sql = ""
        if unity_id is not None:
            scope_sql = "AND r.unity_id = :unity_id"
            params["unity_id"] = int(unity_id)
        elif direction_id is not None:
            unity_ids = await self._scoped_unity_ids(int(direction_id))
            if not unity_ids:
                return []
            scope_sql = "AND r.unity_id IN :unity_ids"
            params["unity_ids"] = unity_ids
            stmt_params.append(bindparam("unity_ids", expanding=True))

        group_label_expr = "d.label" if group_by_direction else "u.label"

        stmt = text(f"""
            SELECT
                r.ref          AS ref,
                r.title        AS title,
                pd.label       AS priority,
                {group_label_expr} AS group_label,
                rs.label       AS status,
                ROUND(GREATEST(TIMESTAMPDIFF(
                    MINUTE, DATE_ADD(r.created_at, INTERVAL r.sla_hours HOUR), NOW()
                ), 0) / 60.0, 1) AS overdue_hours
            FROM request r
            JOIN request_status rs ON rs.id = r.request_status_id
            JOIN priority_definition pd ON pd.id = r.priority_definition_id
            LEFT JOIN unity u ON u.id = r.unity_id
            LEFT JOIN unity d ON d.id = COALESCE(u.parent_direction_id, u.id)
            WHERE r.deleted_at IS NULL
              AND r.sla_breached = 1
              AND rs.code IN :active_statuses
              AND DATE(r.created_at) BETWEEN :start AND :end
              {scope_sql}
            ORDER BY overdue_hours DESC
        """).bindparams(*stmt_params)

        result = await self.session.execute(stmt, params)
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

    async def sla_reopen_stats(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        BR-SLA-REOPEN-001 — statistiques croisées cycles SLA / réouvertures, sur la
        même fenêtre (par défaut) que `sla_report()`. Additif et indépendant :
        ne touche à aucune requête/donnée des rapports existants ci-dessus.
        Calculé depuis les cycles déjà reconstruits par `ModelRequest.sla_cycles`
        (donc depuis `workflow_detail`, append-only) — aucune nouvelle table ni
        colonne. Le premier cycle SLA (`cycle_number == 1`) n'est jamais recalculé
        : ses valeurs proviennent uniquement de l'événement `treatment_completed`
        d'origine, gelé par `ServiceRequest._sla_cycle_snapshot`.
        Note performance : charge en mémoire les demandes + leur historique complet
        sur la période — acceptable pour une fenêtre de rapport habituelle (jours/
        semaines), à revisiter si utilisé sur un historique de plusieurs années.
        """
        from api.models.ModelRequest import Request as RequestModel

        today = date.today()
        s = start_date or (today - timedelta(days=30))
        e = end_date or today
        range_start = datetime.combine(s, datetime.min.time())
        range_end = datetime.combine(e, datetime.min.time()) + timedelta(days=1)

        result = await self.session.execute(
            select(RequestModel)
            # Ni sla_cycles/reopen_count ni interventions n'ont besoin des comptes
            # requester/assignee (seuls `timelines`/`workflows` sont parcourus) —
            # désactiver leur chargement automatique (`lazy="selectin"` par défaut)
            # évite de charger inutilement des comptes hors périmètre de ce rapport.
            .options(noload(RequestModel.assignee), noload(RequestModel.requester))
            .where(
                RequestModel.deleted_at.is_(None),
                RequestModel.created_at >= range_start,
                RequestModel.created_at < range_end,
            )
        )
        requests = result.scalars().unique().all()

        total_tickets = 0
        reopened_tickets = 0
        reopen_counts: list[int] = []
        first_cycle_hours: list[float] = []
        post_reopen_hours: list[float] = []
        closed_first = breached_first = 0
        closed_post = breached_post = 0

        for req in requests:
            if not req.sla_hours or req.sla_hours <= 0:
                continue
            total_tickets += 1
            if req.reopen_count <= 0:
                continue
            reopened_tickets += 1
            reopen_counts.append(req.reopen_count)
            for cycle in req.sla_cycles:
                if not cycle["closed"] or cycle["elapsed_hours"] is None:
                    continue
                if cycle["cycle_number"] == 1:
                    first_cycle_hours.append(cycle["elapsed_hours"])
                    closed_first += 1
                    breached_first += 1 if cycle["breached"] else 0
                else:
                    post_reopen_hours.append(cycle["elapsed_hours"])
                    closed_post += 1
                    breached_post += 1 if cycle["breached"] else 0

        def _avg(values: list[float]) -> Optional[float]:
            return round(sum(values) / len(values), 2) if values else None

        return {
            "report_type": "sla_reopen_stats",
            "period": f"{s.isoformat()} → {e.isoformat()}",
            "total_tickets_with_sla": total_tickets,
            "reopened_tickets": reopened_tickets,
            "reopen_rate": round(reopened_tickets / total_tickets * 100, 1) if total_tickets else 0.0,
            "avg_reopen_count": _avg([float(c) for c in reopen_counts]),
            "avg_first_cycle_hours": _avg(first_cycle_hours),
            "avg_post_reopen_cycle_hours": _avg(post_reopen_hours),
            "first_cycle_sla_compliance_rate": (
                round((closed_first - breached_first) / closed_first * 100, 1) if closed_first else None
            ),
            "post_reopen_sla_compliance_rate": (
                round((closed_post - breached_post) / closed_post * 100, 1) if closed_post else None
            ),
        }

    async def intervention_stats(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        unity_ids: Optional[list[int]] = None,
    ) -> dict:
        """
        BR-TRACE-001 — statistiques agrégées sur les interventions (conteneurs
        logiques du travail d'un intervenant), sur la même fenêtre (par défaut)
        que `sla_report()`/`sla_reopen_stats()`. Additif et indépendant : ne
        touche à aucune requête/donnée des rapports existants. Calculé depuis
        `ModelRequest.interventions` (déjà reconstruit depuis `workflow_detail`,
        données explicitement enregistrées — jamais recalculées ici).
        Note performance : même limite que `sla_reopen_stats` (charge en mémoire
        les demandes + leur historique complet sur la période).
        """
        from api.models.ModelRequest import Request as RequestModel

        today = date.today()
        s = start_date or (today - timedelta(days=30))
        e = end_date or today
        range_start = datetime.combine(s, datetime.min.time())
        range_end = datetime.combine(e, datetime.min.time()) + timedelta(days=1)

        stmt = (
            select(RequestModel)
            # Ni sla_cycles/reopen_count ni interventions n'ont besoin des comptes
            # requester/assignee (seuls `timelines`/`workflows` sont parcourus) —
            # désactiver leur chargement automatique (`lazy="selectin"` par défaut)
            # évite de charger inutilement des comptes hors périmètre de ce rapport.
            .options(noload(RequestModel.assignee), noload(RequestModel.requester))
            .where(
                RequestModel.deleted_at.is_(None),
                RequestModel.created_at >= range_start,
                RequestModel.created_at < range_end,
            )
        )
        if unity_ids is not None:
            clean_unity_ids = [int(uid) for uid in unity_ids if uid is not None]
            if not clean_unity_ids:
                return {
                    "report_type": "intervention_stats",
                    "period": f"{s.isoformat()} → {e.isoformat()}",
                    "total_interventions": 0,
                    "distinct_agents": 0,
                    "avg_duration_hours": None,
                    "total_duration_hours": 0.0,
                    "transmissions": 0,
                    "resolutions": 0,
                    "reopenings": 0,
                    "by_agent": [],
                    "by_service": [],
                    "by_department": [],
                }
            stmt = stmt.where(RequestModel.unity_id.in_(clean_unity_ids))

        result = await self.session.execute(stmt)
        requests = result.scalars().unique().all()

        durations: list[float] = []
        transmissions = resolutions = 0
        reopenings = 0
        distinct_agents: set[str] = set()
        by_agent: dict[str, dict[str, Any]] = {}
        by_service: dict[str, dict[str, Any]] = {}
        by_department: dict[str, dict[str, Any]] = {}

        def _bump(bucket: dict[str, dict[str, Any]], key: Optional[str], label: Optional[str], hours: Optional[float]) -> None:
            if not key:
                return
            entry = bucket.setdefault(key, {"label": label or key, "intervention_count": 0, "total_hours": 0.0})
            entry["intervention_count"] += 1
            if hours is not None:
                entry["total_hours"] += hours

        total_interventions = 0
        for req in requests:
            reopenings += req.reopen_count
            for iv in req.interventions:
                total_interventions += 1
                actor_id = iv.get("actor_id")
                if actor_id:
                    distinct_agents.add(str(actor_id))
                hours = (
                    round(iv["duration_seconds"] / 3600, 2)
                    if iv.get("duration_seconds") is not None else None
                )
                if hours is not None:
                    durations.append(hours)
                if iv.get("decision") == "transmission":
                    transmissions += 1
                elif iv.get("decision") == "resolution":
                    resolutions += 1
                _bump(by_agent, str(actor_id) if actor_id else None, iv.get("actor_name"), hours)
                _bump(by_service, iv.get("actor_service_label"), iv.get("actor_service_label"), hours)
                _bump(by_department, iv.get("actor_department_label"), iv.get("actor_department_label"), hours)

        def _round_bucket(bucket: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            return sorted(
                (
                    {**v, "total_hours": round(v["total_hours"], 2)}
                    for v in bucket.values()
                ),
                key=lambda x: x["total_hours"],
                reverse=True,
            )

        return {
            "report_type": "intervention_stats",
            "period": f"{s.isoformat()} → {e.isoformat()}",
            "total_interventions": total_interventions,
            "distinct_agents": len(distinct_agents),
            "avg_duration_hours": round(sum(durations) / len(durations), 2) if durations else None,
            "total_duration_hours": round(sum(durations), 2) if durations else 0.0,
            "transmissions": transmissions,
            "resolutions": resolutions,
            "reopenings": reopenings,
            "by_agent": _round_bucket(by_agent),
            "by_service": _round_bucket(by_service),
            "by_department": _round_bucket(by_department),
        }
