"""
Routeur rapports & exports — /api/v1/reports/*

Endpoints JSON :
  GET /reports/daily?date=YYYY-MM-DD
  GET /reports/monthly?year=YYYY&month=MM
  GET /reports/by-agent?start=...&end=...&unity_id=...
  GET /reports/by-unity?start=...&end=...
  GET /reports/sla?start=...&end=...

Exports (ajout de ?format=csv|excel|pdf) :
  GET /reports/daily/export
  GET /reports/monthly/export
  GET /reports/by-agent/export
  GET /reports/by-unity/export
  GET /reports/sla/export

Accès : chief, director, dg, admin
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_roles
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
    dependencies=[Depends(require_roles("chief", "director", "dg", "admin"))],
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
    svc: ReportService = Depends(_svc),
):
    """Performance des agents sur une période."""
    return await svc.agent_report(start, end, unity_id)


@router.get("/by-agent/export")
async def export_by_agent(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    unity_id: Optional[int] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport par agent (csv | excel | pdf)."""
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
    svc: ReportService = Depends(_svc),
):
    """Tickets par unité organisationnelle."""
    return await svc.unity_report(start, end)


@router.get("/by-unity/export")
async def export_by_unity(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport par unité (csv | excel | pdf)."""
    rows = await svc.unity_report(start, end)
    cols = ["unity_label", "unity_codename", "total", "resolved", "active", "sla_breached", "resolution_rate"]
    hdrs = ["Service / Unité", "Code", "Total", "Résolus", "Actifs", "SLA breach", "Taux (%)"]

    return _do_export(
        rows, cols, hdrs, fmt,
        filename="rapport_par_service",
        title="Rapport par Service / Unité",
        subtitle="Période : {} → {}".format(start or "J-30", end or "Aujourd'hui"),
    )


# ── Rapport SLA ───────────────────────────────────────────────────────────────

# ── Rapport CSAT ─────────────────────────────────────────────────────────────

@router.get("/csat")
async def csat_report(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    unity_id: Optional[int] = Query(None),
    svc: ReportService = Depends(_svc),
):
    """Rapport CSAT détaillé : résumé + par agent + par catégorie + évolution."""
    return await svc.csat_report(start, end, unity_id)


@router.get("/csat/export")
async def export_csat(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    unity_id: Optional[int] = Query(None),
    fmt: ExportFormat = Query("excel", alias="format"),
    svc: ReportService = Depends(_svc),
):
    """Export du rapport CSAT (csv | excel | pdf)."""
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
