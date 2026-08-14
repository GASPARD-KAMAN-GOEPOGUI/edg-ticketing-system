"""
Routeur rapports & exports — /api/v1/reports/*

Endpoints JSON :
  GET /reports/daily?date=YYYY-MM-DD
  GET /reports/monthly?year=YYYY&month=MM
  GET /reports/by-agent?start=...&end=...&unity_id=...
  GET /reports/by-unity?start=...&end=...&direction_id=...
  GET /reports/decision?start=...&end=...&direction_id=...
  GET /reports/sla?start=...&end=...
  GET /reports/sla/reopen-stats?start=...&end=...
  GET /reports/interventions?start=...&end=...

Exports (ajout de ?format=csv|excel|pdf) :
  GET /reports/daily/export
  GET /reports/monthly/export
  GET /reports/by-agent/export
  GET /reports/by-unity/export
  GET /reports/decision/export
  GET /reports/sla/export
  GET /reports/sla-center/export

Accès : chief, director, admin
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.core.rbac import normalize_role
from api.services.ServiceReport import ReportService
from api.services.ServiceExport import (
    ExportFormat,
    build_response,
    export_csv,
    export_excel,
    export_pdf,
)

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_roles("chief", "director", "admin"))],
)


def _svc(db: AsyncSession = Depends(get_db)) -> ReportService:
    return ReportService(db)


# ── Helpers export ────────────────────────────────────────────────────────────

def _do_export(
    rows: list[dict],
    columns: list[str],
    headers: list[str],
    fmt: ExportFormat,
    filename: str,
    title: str,
    subtitle: str = "",
) -> Response:
    if fmt == "csv":
        data = export_csv(rows, columns)
    elif fmt == "excel":
        data = export_excel(rows, columns, headers=headers, title=title)
    else:
        data = export_pdf(rows, columns, headers=headers, title=title, subtitle=subtitle)
    return build_response(data, fmt, filename)


async def _apply_decision_scope(
    actor,
    direction_id: Optional[int],
    unity_id: Optional[int] | list[int],
    svc: ReportService,
) -> tuple[Optional[int], Optional[int] | list[int]]:
    role = normalize_role(getattr(actor, "role", None))
    if role == "director":
        actor_direction_id = getattr(actor, "direction_id", None)
        direction_id = int(actor_direction_id) if actor_direction_id else -1
    elif role == "chief-departement":
        # Perimetre elargi au departement entier (departement + services rattaches),
        # cf. BR-ROLE-CHIEF-DEPARTEMENT-001 deja applique ailleurs (ticket_actions.py,
        # RouteRequest.py) — sans quoi la vue agregee par service (Lot 3) ne remonterait
        # que le seul service du chef-departement au lieu de tout son departement.
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = await svc._scoped_unity_ids(int(actor_unity_id)) if actor_unity_id else [-1]
    elif role == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
    return direction_id, unity_id


async def _apply_intervention_scope(actor, svc: ReportService) -> list[int] | None:
    """Retourne le périmètre organisationnel sûr pour les rapports d'interventions.

    `None` signifie périmètre global explicitement autorisé (admin uniquement).
    Une liste vide force une réponse vide et évite tout repli global accidentel.
    """
    role = normalize_role(getattr(actor, "role", None))
    if role == "admin":
        return None
    if role == "director":
        actor_direction_id = (
            getattr(actor, "direction_id", None)
            or getattr(actor, "unity_id", None)
            or getattr(actor, "unit_id", None)
        )
        return await svc._scoped_unity_ids(int(actor_direction_id)) if actor_direction_id else []
    if role == "chief-departement":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        return await svc._scoped_unity_ids(int(actor_unity_id)) if actor_unity_id else []
    if role == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        return [int(actor_unity_id)] if actor_unity_id else []
    return []


# ── Rapport journalier ────────────────────────────────────────────────────────

@router.get("/daily")
async def daily_report(
    report_date: Optional[date] = Query(None, alias="date"),
    svc: ReportService = Depends(_svc),
):
    """Rapport journalier complet (défaut = aujourd'hui)."""
    return await svc.daily_report(report_date)


@router.get("/daily/export")
async def export_daily(
    report_date: Optional[date] = Query(None, alias="date"),
    fmt: ExportFormat = Query("excel", alias="format"),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport journalier (csv | excel | pdf)."""
    data = await svc.daily_report(report_date)
    d = data["date"]
    rows = data["by_category"]
    cols = ["category", "total"]
    hdrs = ["Catégorie", "Total"]

    # On enrichit avec le résumé en première ligne
    summary_row = {
        "category": "RÉSUMÉ GLOBAL",
        "total": data["summary"]["total_created"],
    }
    rows = [summary_row] + rows

    return _do_export(
        rows, cols, hdrs, fmt,
        filename=f"rapport_journalier_{d}",
        title=f"Rapport Journalier — {d}",
        subtitle=f"Créés: {data['summary']['total_created']} | Résolus: {data['summary']['total_resolved']} | SLA breach: {data['summary']['sla_breached']}",
    )


# ── Rapport mensuel ───────────────────────────────────────────────────────────

@router.get("/monthly")
async def monthly_report(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    svc: ReportService = Depends(_svc),
):
    """Rapport mensuel avec évolution quotidienne."""
    return await svc.monthly_report(year, month)


@router.get("/monthly/export")
async def export_monthly(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    fmt: ExportFormat = Query("excel", alias="format"),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport mensuel (csv | excel | pdf)."""
    data = await svc.monthly_report(year, month)
    rows = data["daily_evolution"]
    cols = ["day", "created", "resolved"]
    hdrs = ["Date", "Créés", "Résolus"]
    period = f"{data['year']}-{data['month']:02d}"

    return _do_export(
        rows, cols, hdrs, fmt,
        filename=f"rapport_mensuel_{period}",
        title=f"Rapport Mensuel — {period}",
        subtitle=f"Total créés: {data['summary']['total_created']} | Taux résolution: {data['summary']['resolution_rate']}% | SLA: {data['summary']['sla_compliance_rate']}%",
    )


# ── Rapport par agent ─────────────────────────────────────────────────────────

@router.get("/by-agent")
async def agent_report(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    unity_id: Optional[int] = Query(None),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Performance des agents sur une période."""
    if normalize_role(getattr(actor, "role", None)) == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
    return await svc.agent_report(start, end, unity_id)


@router.get("/by-agent/export")
async def export_by_agent(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    unity_id: Optional[int] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport par agent (csv | excel | pdf)."""
    if normalize_role(getattr(actor, "role", None)) == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
    rows = await svc.agent_report(start, end, unity_id)
    cols = ["agent_name", "unity_label", "assigned_total", "resolved_total", "escalated_total", "avg_resolution_hours", "resolution_rate"]
    hdrs = ["Agent", "Unité", "Assignés", "Résolus", "Escaladés", "Moy. résolution (h)", "Taux (%)"]

    return _do_export(
        rows, cols, hdrs, fmt,
        filename="rapport_agents",
        title="Rapport Performance Agents",
        subtitle="Période : {} → {}".format(start or "J-30", end or "Aujourd'hui"),
    )


# ── Rapport par unité (service) ───────────────────────────────────────────────

@router.get("/by-unity")
async def unity_report(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    direction_id: Optional[int] = Query(None),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Tickets par unité organisationnelle."""
    role = normalize_role(getattr(actor, "role", None))
    unity_id = None
    if role == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
        direction_id = None
    elif role == "director":
        direction_id = int(actor.direction_id) if actor.direction_id else None
    return await svc.unity_report(start, end, direction_id=direction_id, unity_id=unity_id)


@router.get("/by-unity/export")
async def export_by_unity(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    direction_id: Optional[int] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport par unité (csv | excel | pdf)."""
    role = normalize_role(getattr(actor, "role", None))
    unity_id = None
    if role == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
        direction_id = None
    elif role == "director":
        direction_id = int(actor.direction_id) if actor.direction_id else None
    rows = await svc.unity_report(start, end, direction_id=direction_id, unity_id=unity_id)
    cols = ["unity_label", "unity_codename", "total", "resolved", "active", "sla_breached", "resolution_rate"]
    hdrs = ["Service / Unité", "Code", "Total", "Résolus", "Actifs", "SLA breach", "Taux (%)"]

    return _do_export(
        rows, cols, hdrs, fmt,
        filename="rapport_par_service",
        title="Rapport par Service / Unité",
        subtitle="Période : {} → {}".format(start or "J-30", end or "Aujourd'hui"),
    )


# ── Rapport décisionnel ──────────────────────────────────────────────────────

@router.get("/decision")
async def decision_report(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    direction_id: Optional[int] = Query(None),
    unity_id: Optional[int] = Query(None),
    assignee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    group_by: Literal["direction", "service", "status", "category", "priority", "assignee", "period"] = Query("service"),
    inactive_days: int = Query(3, ge=0, le=365),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    sort_by: str = Query("created_at"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    include_tickets: bool = Query(False),
    include_audit_rows: bool = Query(False),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Moteur décisionnel EDG → direction → service → agent → ticket."""
    scoped_direction_id, scoped_unity_id = await _apply_decision_scope(actor, direction_id, unity_id, svc)
    return await svc.decision_report(
        start,
        end,
        direction_id=scoped_direction_id,
        unity_id=scoped_unity_id,
        assignee_id=assignee_id,
        status=status,
        category=category,
        priority=priority,
        source=source,
        origin=origin,
        search=search,
        group_by=group_by,
        inactive_days=inactive_days,
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        include_tickets=include_tickets,
        include_audit_rows=include_audit_rows,
        generated_by=getattr(actor, "email", None) or getattr(actor, "name", None),
    )


@router.get("/decision/export")
async def export_decision_report(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    direction_id: Optional[int] = Query(None),
    unity_id: Optional[int] = Query(None),
    assignee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    group_by: Literal["global", "executive", "direction", "service", "status", "category", "priority", "assignee", "period", "audit"] = Query("direction"),
    inactive_days: int = Query(3, ge=0, le=365),
    sort_by: str = Query("total_tickets"),
    sort_dir: Literal["asc", "desc"] = Query("desc"),
    fmt: ExportFormat = Query("excel", alias="format"),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport décisionnel avec les filtres appliqués."""
    scoped_direction_id, scoped_unity_id = await _apply_decision_scope(actor, direction_id, unity_id, svc)
    data = await svc.decision_report(
        start,
        end,
        direction_id=scoped_direction_id,
        unity_id=scoped_unity_id,
        assignee_id=assignee_id,
        status=status,
        category=category,
        priority=priority,
        source=source,
        origin=origin,
        search=search,
        group_by=("service" if group_by in {"global", "executive", "audit"} else group_by),
        inactive_days=inactive_days,
        page=1,
        limit=500,
        sort_by=sort_by,
        sort_dir=sort_dir,
        include_tickets=False,
        include_audit_rows=group_by == "audit",
        generated_by=getattr(actor, "email", None) or getattr(actor, "name", None),
    )
    rows = svc.decision_export_rows(data, group_by=group_by)
    cols = list(rows[0].keys()) if rows else ["periode", "genere_le", "genere_par", "filtres"]
    hdrs = cols

    return _do_export(
        rows,
        cols,
        hdrs,
        fmt,
        filename=f"rapport_decisionnel_{group_by}",
        title="Rapport décisionnel EDG",
        subtitle="Période : {} → {} | Groupe : {}".format(
            data["period"]["start"],
            data["period"]["end"],
            group_by,
        ),
    )


# ── Rapport SLA ───────────────────────────────────────────────────────────────

# ── Rapport CSAT ─────────────────────────────────────────────────────────────

@router.get("/csat")
async def csat_report(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    unity_id: Optional[int] = Query(None),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Rapport CSAT détaillé : résumé + par agent + par catégorie + évolution."""
    if normalize_role(getattr(actor, "role", None)) == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
    return await svc.csat_report(start, end, unity_id)


@router.get("/csat/export")
async def export_csat(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    unity_id: Optional[int] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport CSAT (csv | excel | pdf)."""
    if normalize_role(getattr(actor, "role", None)) == "chief-service":
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
    data = await svc.csat_report(start, end, unity_id)
    rows = data["by_agent"]
    cols = ["agent_name", "unity_label", "total_ratings", "avg_rating", "satisfied_count"]
    hdrs = ["Agent", "Unité", "Nb évaluations", "Note moy.", "Satisfaits"]

    # Insère une ligne de résumé global
    s_row = data["summary"]
    rows = [{
        "agent_name": "GLOBAL",
        "unity_label": "",
        "total_ratings": s_row["total_ratings"],
        "avg_rating": s_row["avg_rating"],
        "satisfied_count": s_row["satisfied_count"],
    }] + rows

    return _do_export(
        rows, cols, hdrs, fmt,
        filename="rapport_csat",
        title="Rapport CSAT — Satisfaction Client",
        subtitle=(
            f"Période : {data['period']} | "
            f"Note moy. : {s_row['avg_rating']} | "
            f"Taux satisfaction : {s_row['satisfaction_rate']}%"
        ),
    )


# ── Rapport SLA ───────────────────────────────────────────────────────────────

@router.get("/sla")
async def sla_report(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    svc: ReportService = Depends(_svc),
):
    """Rapport de conformité SLA."""
    return await svc.sla_report(start, end)


@router.get("/sla/export")
async def export_sla(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport SLA (csv | excel | pdf)."""
    data = await svc.sla_report(start, end)
    rows = [{
        "Période": data["period"],
        "Tickets avec SLA": data["total_with_sla"],
        "Résolus dans les délais": data["resolved_in_sla"],
        "En retard actuel": data["currently_breached"],
        "Résolus en retard": data["resolved_late"],
        "Taux conformité (%)": data["compliance_rate"],
        "Moy. résolution (min)": data["avg_resolution_min"],
    }]
    cols = list(rows[0].keys())

    return _do_export(
        rows, cols, cols, fmt,
        filename="rapport_sla",
        title="Rapport Conformité SLA",
        subtitle=data["period"],
    )


@router.get("/sla-center/export")
async def export_sla_center(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """Export du Centre SLA : tickets actifs en dépassement SLA sur la période choisie
    (mêmes règles/périmètre que la page — cf. sla_center_breach_rows)."""
    role = normalize_role(getattr(actor, "role", None))
    direction_id: Optional[int] = None
    unity_id: Optional[int] = None
    group_by_direction = False
    if role in ("chief-service", "chief-departement"):
        actor_unity_id = getattr(actor, "unity_id", None) or getattr(actor, "unit_id", None)
        unity_id = int(actor_unity_id) if actor_unity_id else -1
    elif role == "director":
        direction_id = int(actor.direction_id) if actor.direction_id else -1
    else:
        group_by_direction = True

    rows = await svc.sla_center_breach_rows(
        start, end,
        direction_id=direction_id,
        unity_id=unity_id,
        group_by_direction=group_by_direction,
    )
    cols = ["ref", "title", "priority", "group_label", "status", "overdue_hours"]
    hdrs = [
        "Référence", "Titre", "Priorité",
        "Direction" if group_by_direction else "Service",
        "Statut", "Dépassement (h)",
    ]

    return _do_export(
        rows, cols, hdrs, fmt,
        filename="rapport_sla_center",
        title="Centre SLA — Tickets en dépassement",
        subtitle="Période : {} → {}".format(start or "J-30", end or "Aujourd'hui"),
    )


@router.get("/sla/reopen-stats")
async def sla_reopen_stats(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    svc: ReportService = Depends(_svc),
):
    """BR-SLA-REOPEN-001 — statistiques croisées cycles SLA / réouvertures
    (tickets réouverts, durée moyenne 1er traitement vs après réouverture,
    nombre moyen de réouvertures, conformité SLA par type de cycle)."""
    return await svc.sla_reopen_stats(start, end)


@router.get("/interventions")
async def intervention_stats(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    actor=Depends(get_current_user),
    svc: ReportService = Depends(_svc),
):
    """BR-TRACE-001 — statistiques agrégées sur les interventions (nombre,
    intervenants distincts, durée moyenne/cumulée, transmissions/résolutions/
    réouvertures, temps passé par agent/service/département)."""
    unity_ids = await _apply_intervention_scope(actor, svc)
    return await svc.intervention_stats(start, end, unity_ids=unity_ids)
