"""
RouteEscalation — /escalations

Les escalades ne sont pas une table dédiée : elles sont stockées comme événements
dans workflow_detail (event_type='escalation_manual').
Ce router expose le CRUD attendu par le frontend via des JOINs vers Workflow et Request.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_roles
from api.models.ModelRequest import Request
from api.models.ModelWorkflow import Workflow
from api.models.ModelWorkflowDetail import WorkflowDetail
from api.schemas.SchemaEscalation import EscalationResponse, PaginatedEscalations

class _ResolveBody(BaseModel):
    dg_comment: Optional[str] = None
    action: Optional[str] = "resolve"  # "resolve" | "reject"


router = APIRouter(
    prefix="/escalations",
    tags=["Escalations"],
    dependencies=[Depends(require_roles("agent", "chief", "director", "dg", "admin"))],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _base_stmt():
    """Stmt de base : WorkflowDetail JOIN Workflow JOIN Request, event_type=escalation_manual."""
    return (
        select(WorkflowDetail, Workflow.request_id, Request.ref)
        .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
        .join(Request, Workflow.request_id == Request.id)
        .where(WorkflowDetail.event_type == "escalation_manual")
        .where(WorkflowDetail.deleted_at.is_(None))
    )


async def _fetch_one(db: AsyncSession, escalation_id: int):
    """Retourne (WorkflowDetail, request_id, ref) ou lève 404."""
    row = (await db.execute(
        _base_stmt().where(WorkflowDetail.id == escalation_id)
    )).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalade introuvable.")
    return row


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedEscalations)
async def list_escalations(
    status_filter: Optional[str] = Query(None, alias="status"),
    level: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Liste toutes les escalades (workflow_detail event_type='escalation_manual').
    Filtrages optionnels : status (open/reviewed/resolved) et level.
    """
    stmt = _base_stmt().order_by(WorkflowDetail.created_at.desc())

    # Comptage total (avant pagination)
    count_sub = stmt.subquery()
    total: int = (await db.scalar(select(func.count()).select_from(count_sub))) or 0

    rows = (await db.execute(stmt.offset((page - 1) * limit).limit(limit))).all()

    items: list[EscalationResponse] = []
    for wd, req_id, ref in rows:
        esc = EscalationResponse.from_detail(wd, req_id, ref)
        # Filtres JSON (niveau et statut stockés dans infos)
        if status_filter and esc.escalation_status != status_filter:
            continue
        if level and esc.level != level:
            continue
        items.append(esc)

    pages = max(1, (total + limit - 1) // limit)
    return PaginatedEscalations(items=items, total=total, page=page, pages=pages)


@router.get("/{id}", response_model=EscalationResponse)
async def get_escalation(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retourne le détail d'une escalade par son ID."""
    wd, req_id, ref = await _fetch_one(db, id)
    return EscalationResponse.from_detail(wd, req_id, ref)


@router.patch("/{id}/review", response_model=EscalationResponse)
async def review_escalation(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Marque une escalade comme prise en compte (status → reviewed)."""
    wd, req_id, ref = await _fetch_one(db, id)
    infos = dict(wd.infos or {})
    infos["status"] = "reviewed"
    wd.infos = infos
    db.add(wd)
    await db.commit()
    await db.refresh(wd)
    return EscalationResponse.from_detail(wd, req_id, ref)


@router.patch("/{id}/resolve", response_model=EscalationResponse)
async def resolve_escalation(
    id: int,
    body: _ResolveBody = Body(default_factory=_ResolveBody),
    db: AsyncSession = Depends(get_db),
):
    """Résout ou rejette une escalade. Body : {dg_comment, action: 'resolve'|'reject'}."""
    wd, req_id, ref = await _fetch_one(db, id)
    infos = dict(wd.infos or {})
    infos["status"] = "resolved" if body.action != "reject" else "rejected"
    if body.dg_comment:
        infos["dg_comment"] = body.dg_comment
    wd.infos = infos
    db.add(wd)
    await db.commit()
    await db.refresh(wd)
    return EscalationResponse.from_detail(wd, req_id, ref)
