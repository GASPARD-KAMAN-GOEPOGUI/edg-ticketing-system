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

from api.core.rbac import normalize_role
from api.dependencies import get_db, require_roles
from api.models.ModelOrganigram import Organigram
from api.models.ModelRequest import Request
from api.models.ModelUnity import Unity
from api.models.ModelWorkflow import Workflow
from api.models.ModelWorkflowDetail import WorkflowDetail
from api.schemas.SchemaEscalation import EscalationResponse, PaginatedEscalations

class _ResolveBody(BaseModel):
    decision_comment: Optional[str] = None
    dg_comment: Optional[str] = None
    action: Optional[str] = "resolve"  # "resolve" | "reject"


router = APIRouter(
    prefix="/escalations",
    tags=["Escalations"],
    dependencies=[Depends(require_roles("agent", "chief", "director", "admin"))],
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


async def _direction_unity_ids(db: AsyncSession, direction_id: int | str | None) -> set[int]:
    if direction_id is None:
        return set()
    try:
        root_id = int(direction_id)
    except (TypeError, ValueError):
        return set()

    ids: set[int] = {root_id}
    org_row = await db.execute(
        select(Organigram.id)
        .where(Organigram.unity_id == root_id, Organigram.deleted_at.is_(None))
        .limit(1)
    )
    org_id = org_row.scalar_one_or_none()
    if org_id:
        child_rows = await db.execute(
            select(Organigram.unity_id)
            .where(Organigram.parent_id == org_id, Organigram.deleted_at.is_(None))
        )
        ids.update(int(uid) for (uid,) in child_rows.all() if uid is not None)

    unity_rows = await db.execute(
        select(Unity.id)
        .where(Unity.parent_direction_id == root_id, Unity.deleted_at.is_(None))
    )
    ids.update(int(uid) for (uid,) in unity_rows.all() if uid is not None)
    return ids


async def _scope_stmt(stmt, db: AsyncSession, actor):
    role = normalize_role(getattr(actor, "role", None))
    actor_id = getattr(actor, "id", None)
    unity_id = getattr(actor, "unity_id", None)

    if role == "admin":
        return stmt

    if role == "director":
        allowed_ids = await _direction_unity_ids(db, unity_id)
        if not allowed_ids:
            return stmt.where(False)
        return stmt.where(Request.unity_id.in_(allowed_ids))

    if role in {"chief", "agent"}:
        if unity_id is None and actor_id is None:
            return stmt.where(False)
        clauses = []
        if unity_id is not None:
            clauses.append(Request.unity_id == unity_id)
        if actor_id is not None:
            clauses.append(Request.assignee_id == actor_id)
        from sqlalchemy import or_
        return stmt.where(or_(*clauses))

    return stmt.where(False)


async def _fetch_one(db: AsyncSession, escalation_id: int, actor):
    """Retourne (WorkflowDetail, request_id, ref) ou lève 404."""
    stmt = await _scope_stmt(_base_stmt(), db, actor)
    row = (await db.execute(
        stmt.where(WorkflowDetail.id == escalation_id)
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
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
):
    """
    Liste toutes les escalades (workflow_detail event_type='escalation_manual').
    Filtrages optionnels : status (open/reviewed/resolved) et level.
    """
    stmt = await _scope_stmt(_base_stmt(), db, actor)
    stmt = stmt.order_by(WorkflowDetail.created_at.desc())

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
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
):
    """Retourne le détail d'une escalade par son ID."""
    wd, req_id, ref = await _fetch_one(db, id, actor)
    return EscalationResponse.from_detail(wd, req_id, ref)


@router.put("/{id}/review", response_model=EscalationResponse)
async def review_escalation(
    id: int,
    db: AsyncSession = Depends(get_db),
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
):
    """Marque une escalade comme prise en compte (status → reviewed)."""
    wd, req_id, ref = await _fetch_one(db, id, actor)
    infos = dict(wd.infos or {})
    infos["status"] = "reviewed"
    wd.infos = infos
    db.add(wd)
    await db.commit()
    await db.refresh(wd)
    return EscalationResponse.from_detail(wd, req_id, ref)


@router.put("/{id}/resolve", response_model=EscalationResponse)
async def resolve_escalation(
    id: int,
    body: _ResolveBody = Body(default_factory=_ResolveBody),
    db: AsyncSession = Depends(get_db),
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
):
    """Résout ou rejette une escalade. Body : {decision_comment, action}."""
    wd, req_id, ref = await _fetch_one(db, id, actor)
    infos = dict(wd.infos or {})
    infos["status"] = "resolved" if body.action != "reject" else "rejected"
    decision_comment = body.decision_comment or body.dg_comment
    if decision_comment:
        infos["decision_comment"] = decision_comment
    wd.infos = infos
    db.add(wd)
    await db.commit()
    await db.refresh(wd)
    return EscalationResponse.from_detail(wd, req_id, ref)
