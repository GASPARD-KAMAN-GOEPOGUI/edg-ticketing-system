"""
Routes de statistiques opérationnelles — EDG Connect.
Préfixe : /stats  (complète RouteCsatStats.py qui couvre /stats/csat*)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.services.ServiceStats import StatsService

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(require_roles("chief", "director", "dg", "admin"))],
)

# Router séparé sans guard de rôle restrictif — pour les agents
agent_router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> StatsService:
    return StatsService(db)


@agent_router.get("/my")
async def my_stats(
    actor=Depends(get_current_user),
    svc: StatsService = Depends(_svc),
):
    """Stats personnelles de l'agent connecté (assigné, résolu, SLA, temps moyen)."""
    if actor.role not in ("agent", "chief", "director", "dg", "admin"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    return await svc.my_stats(int(actor.id))


# ── KPIs globaux ──────────────────────────────────────────────────────────────

@router.get("/global")
async def global_kpis(
    _=Depends(require_roles("dg", "admin")),
    svc: StatsService = Depends(_svc),
):
    """KPIs globaux — réservé DG et Admin."""
    return await svc.global_kpis()


# ── Dashboard contextuel ──────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard_summary(
    direction_id: Optional[int] = Query(None),
    unit_id: Optional[int] = Query(None),
    actor=Depends(get_current_user),
    svc: StatsService = Depends(_svc),
):
    """
    Résumé dashboard filtré selon le périmètre de l'utilisateur connecté.
    chief → périmètre unité; director → périmètre direction; dg/admin → global.
    """
    # Forçage RBAC — le paramètre client est ignoré (même correction que C-N°3)
    if actor.role == "chief":
        unit_id = int(actor.unit_id) if actor.unit_id else None
        direction_id = None
    elif actor.role == "director":
        direction_id = int(actor.direction_id) if actor.direction_id else None
        unit_id = None
    # dg et admin voient tout sans restriction
    return await svc.dashboard_summary(direction_id=direction_id, unit_id=unit_id)


# ── Breakdowns ────────────────────────────────────────────────────────────────

@router.get("/by-direction")
async def stats_by_direction(svc: StatsService = Depends(_svc)):
    """
    Requêtes groupées par direction (total, résolus, actifs, SLA breach).
    Utilisé par le dashboard DG et les vues de supervision.
    """
    return await svc.requests_by_direction()


@router.get("/by-unit")
async def stats_by_unit(svc: StatsService = Depends(_svc)):
    """Requêtes groupées par unité (avec direction parent)."""
    return await svc.requests_by_unit()


@router.get("/by-period")
async def stats_by_period(
    days: int = Query(30, ge=7, le=365),
    svc: StatsService = Depends(_svc),
):
    """
    Évolution quotidienne des requêtes sur N jours (pour graphiques Recharts).
    Retourne: day, total, resolved, external.
    """
    return await svc.requests_by_period(days=days)


@router.get("/by-category")
async def stats_by_category(svc: StatsService = Depends(_svc)):
    """Breakdown par catégorie de requête avec taux de résolution."""
    return await svc.requests_by_category()


@router.get("/by-priority")
async def stats_by_priority(svc: StatsService = Depends(_svc)):
    """Breakdown par niveau de priorité avec SLA breach par niveau."""
    return await svc.requests_by_priority()


# ── Performance agents ────────────────────────────────────────────────────────

@router.get("/by-agent")
async def stats_by_agent(
    direction_id: Optional[int] = Query(None),
    unit_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(get_current_user),
    svc: StatsService = Depends(_svc),
):
    """
    Performance par agent : assignées, résolues, temps moyen de résolution.
    Scope RBAC forcé : chief → son unité, director → sa direction, dg/admin → global.
    """
    if actor.role == "chief":
        unit_id = int(actor.unit_id) if actor.unit_id else None
        direction_id = None
    elif actor.role == "director":
        direction_id = int(actor.direction_id) if actor.direction_id else None
        unit_id = None
    # dg et admin voient tout
    return await svc.agent_performance(direction_id=direction_id, unit_id=unit_id, limit=limit)


# ── Escalades ─────────────────────────────────────────────────────────────────

@router.get("/escalations")
async def stats_escalations(svc: StatsService = Depends(_svc)):
    """Stats escalades : par statut, par niveau (L1/L2/L3), créées aujourd'hui."""
    return await svc.escalation_stats()


# ── SLA ───────────────────────────────────────────────────────────────────────

@router.get("/sla")
async def stats_sla(
    direction_id: Optional[int] = Query(None),
    svc: StatsService = Depends(_svc),
):
    """
    Conformité SLA : taux de conformité, breach actuel, résolutions tardives, temps moyen.
    Filtrable par direction.
    """
    return await svc.sla_compliance(direction_id=direction_id)
