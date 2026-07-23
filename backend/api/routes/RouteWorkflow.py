from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaWorkflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from api.schemas.SchemaWorkflowDetail import (
    WorkflowDetailUpdate,
    WorkflowDetailResponse,
    WorkflowDetailStepSchema,
    WorkflowDetailAcceptSchema,
)
from api.schemas.base import PaginatedResponse
from api.services import WorkflowService

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
    dependencies=[Depends(get_current_user)],
)
request_workflow_router = APIRouter(
    prefix="/requests",
    tags=["workflows"],
    dependencies=[Depends(get_current_user)],
)
# Router top-level pour les étapes (pattern edgrh /v1/detail-workflow/)
workflow_detail_router = APIRouter(
    prefix="/workflow-details",
    tags=["workflow-details"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> WorkflowService:
    return WorkflowService(db)


def _actor_display_name(actor) -> str | None:
    parts = [getattr(actor, "firstname", None), getattr(actor, "name", None)]
    return " ".join(part for part in parts if part) or None


# ── Request-scoped workflow endpoints ─────────────────────────────────────────

class WorkflowCreateBody(BaseModel):
    workflow_status: str = "active"
    infos: Optional[Any] = None


class AutoCircuitBody(BaseModel):
    unit_id: Optional[int] = None
    direction_id: Optional[int] = None
    workflow_status: str = "active"


class WorkflowDetailBody(BaseModel):
    unity_id: Optional[str] = None
    unit_id: Optional[str] = None
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    parent_id: Optional[str] = None
    accepted: Optional[bool] = None
    activated: bool = False
    infos: Optional[Any] = None


class AcceptedDetailBody(BaseModel):
    """Pattern edgrh AcceptedDetailWorkflowBaseSchema — body pour PUT /accepted."""
    id: int
    accepted: bool
    comment: Optional[str] = None


_staff = Depends(require_roles("agent", "chief", "director", "admin"))


@request_workflow_router.get(
    "/{request_id}/workflow",
    response_model=list[WorkflowResponse],
)
async def list_request_workflows(
    request_id: str,
    _=_staff,
    svc: WorkflowService = Depends(_svc),
):
    return await svc.get_by_request(request_id)


@request_workflow_router.post(
    "/{request_id}/workflow",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_request_workflow(
    request_id: str,
    body: WorkflowCreateBody,
    _=Depends(require_roles("agent", "chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.create_for_request(request_id, body.dict(exclude_unset=True))


@request_workflow_router.post(
    "/{request_id}/workflow/auto-circuit",
    status_code=status.HTTP_201_CREATED,
    summary="Créer un workflow + circuit automatique (pattern edgrh)",
    description=(
        "Crée un workflow pour la demande et construit automatiquement le circuit de validation "
        "en cherchant les chefs d'unité (unit_id) puis les directeurs (direction_id). "
        "La première étape est immédiatement activée."
    ),
)
async def create_auto_circuit(
    request_id: str,
    body: AutoCircuitBody,
    actor=Depends(require_roles("agent", "chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.create_for_request_with_auto_circuit(
        request_id,
        unit_id=body.unit_id,
        direction_id=body.direction_id,
        workflow_status=body.workflow_status,
        actor_id=str(actor.id),
    )


# ── Workflow CRUD ─────────────────────────────────────────────────────────────

@router.get(
    "/search/",
    response_model=PaginatedResponse,
    summary="Recherche multi-critères de workflows (pattern edgrh /search/)",
)
async def search_workflows(
    request_id: Optional[int] = Query(None),
    workflow_status: Optional[str] = Query(None),
    uuid: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _=_staff,
    svc: WorkflowService = Depends(_svc),
):
    return await svc.search_workflows(
        request_id=request_id,
        workflow_status=workflow_status,
        uuid=uuid,
        page=page,
        limit=limit,
    )


@router.get("/", response_model=PaginatedResponse)
async def list_workflows(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: WorkflowService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/by-request/{request_id}", response_model=list[WorkflowResponse])
async def list_by_request(request_id: str, _=_staff, svc: WorkflowService = Depends(_svc)):
    return await svc.get_by_request(request_id)


@router.get("/active/by-request/{request_id}", response_model=WorkflowResponse)
async def get_active_for_request(request_id: str, _=_staff, svc: WorkflowService = Depends(_svc)):
    return await svc.get_active_for_request(request_id)


@router.get("/{id}", response_model=WorkflowResponse)
async def get_workflow(id: str, _=_staff, svc: WorkflowService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: WorkflowCreate,
    _=Depends(require_roles("agent", "chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.patch("/{id}", response_model=WorkflowResponse)
async def update_workflow(
    id: str,
    body: WorkflowUpdate,
    _=Depends(require_roles("agent", "chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.post("/{id}/complete", response_model=WorkflowResponse)
async def complete_workflow(
    id: str,
    _=Depends(require_roles("agent", "chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.complete(id)


@router.post("/{id}/suspend", response_model=WorkflowResponse)
async def suspend_workflow(
    id: str,
    _=Depends(require_roles("chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.suspend(id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    id: str,
    _=Depends(require_roles("admin")),
    svc: WorkflowService = Depends(_svc),
):
    await svc.delete(id)


@router.put(
    "/{id}/restore",
    response_model=WorkflowResponse,
    summary="Restaurer un workflow soft-deleted (pattern edgrh /restore/{id})",
)
async def restore_workflow(
    id: str,
    _=Depends(require_roles("admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.restore_workflow(id)


# ── Workflow Details ──────────────────────────────────────────────────────────

@router.get("/{id}/details", response_model=list[WorkflowDetailResponse])
async def list_workflow_details(id: str, _=_staff, svc: WorkflowService = Depends(_svc)):
    return await svc.list_details(id)


@router.post(
    "/{id}/details",
    response_model=WorkflowDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_detail(
    id: str,
    body: WorkflowDetailBody,
    _=Depends(require_roles("chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    data = body.dict(exclude_unset=True)
    if data.get("unit_id") and not data.get("unity_id"):
        data["unity_id"] = data["unit_id"]
    data.pop("unit_id", None)
    data["workflow_id"] = id
    return await svc.create_detail(data)


@router.patch("/{id}/details/{detail_id}", response_model=WorkflowDetailResponse)
async def update_workflow_detail(
    id: str,
    detail_id: str,
    body: WorkflowDetailUpdate,
    _=Depends(require_roles("agent", "chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.update_detail(detail_id, body.dict(exclude_unset=True))


@router.post(
    "/{id}/details/{detail_id}/accept",
    response_model=WorkflowDetailResponse,
    summary="Accepter ou refuser une étape du workflow",
    description=(
        "Valide ou refuse une étape. "
        "Si acceptée, l'étape suivante est automatiquement activée. "
        "Si c'était la dernière étape, le workflow passe en 'completed'. "
        "Si refusée, le workflow passe en 'suspended'."
    ),
)
async def accept_workflow_detail(
    id: str,
    detail_id: str,
    body: WorkflowDetailAcceptSchema,
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.accept_detail(
        detail_id,
        agent_id=str(actor.id),
        actor_name=_actor_display_name(actor) or getattr(actor, "name", None),
        actor_role=getattr(actor, "role", None),
        actor=actor,
        accepted=body.accepted,
        comment=body.comment,
    )


@router.get(
    "/{id}/details/current",
    response_model=WorkflowDetailResponse,
    summary="Étape active en attente de décision",
)
async def get_current_step(
    id: str,
    _=_staff,
    svc: WorkflowService = Depends(_svc),
):
    step = await svc.get_current_step(id)
    if step is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Aucune étape active en attente pour ce workflow.")
    return step


@router.post(
    "/{id}/details/circuit",
    response_model=list[WorkflowDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un circuit complet d'étapes en une fois",
    description=(
        "Crée toutes les étapes du circuit dans l'ordre fourni. "
        "La première étape est automatiquement activée. "
        "Les suivantes s'activent au fur et à mesure des validations."
    ),
)
async def create_circuit(
    id: str,
    body: list[WorkflowDetailStepSchema],
    _=Depends(require_roles("chief", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    steps = [s.dict(exclude_unset=True) for s in body]
    return await svc.create_circuit(id, steps)


@router.get(
    "/{id}/details/search/",
    response_model=PaginatedResponse,
    summary="Recherche multi-critères des étapes d'un workflow",
)
async def search_workflow_details(
    id: str,
    agent_id: Optional[int] = Query(None),
    unit_id: Optional[int] = Query(None),
    activated: Optional[bool] = Query(None),
    accepted: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    _=_staff,
    svc: WorkflowService = Depends(_svc),
):
    """Filtre les étapes d'un workflow donné — pattern edgrh DetailWorkflowRouter /search/."""
    return await svc.search_details(
        workflow_id=int(id),
        agent_id=agent_id,
        unit_id=unit_id,
        activated=activated,
        accepted=accepted,
        page=page,
        limit=limit,
    )


@router.put(
    "/{id}/details/{detail_id}/restore",
    response_model=WorkflowDetailResponse,
    summary="Restaurer une étape soft-deleted",
)
async def restore_workflow_detail(
    id: str,
    detail_id: str,
    _=Depends(require_roles("admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.restore_detail(detail_id)


# ── Router top-level workflow-details (pattern edgrh /v1/detail-workflow/) ────

@workflow_detail_router.get(
    "/search/",
    response_model=PaginatedResponse,
    summary="Recherche cross-workflow des étapes (pattern edgrh /detail-workflow/search/)",
)
async def search_all_workflow_details(
    workflow_id: Optional[int] = Query(None),
    agent_id: Optional[int] = Query(None),
    unit_id: Optional[int] = Query(None),
    activated: Optional[bool] = Query(None),
    accepted: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    _=_staff,
    svc: WorkflowService = Depends(_svc),
):
    """
    Recherche d'étapes sans être limité à un seul workflow.
    Reproduit DetailWorkflowRouter.get_search() d'edgrh.
    """
    return await svc.search_details(
        workflow_id=workflow_id,
        agent_id=agent_id,
        unit_id=unit_id,
        activated=activated,
        accepted=accepted,
        page=page,
        limit=limit,
    )


@workflow_detail_router.put(
    "/accepted",
    response_model=WorkflowDetailResponse,
    summary="Accepter/refuser une étape (pattern edgrh PUT /detail-workflow/accepted/)",
    description=(
        "Corps : {id, accepted, comment?}. "
        "Si accepté → étape suivante activée. "
        "Si refusé → workflow suspendu."
    ),
)
async def accepted_detail(
    body: AcceptedDetailBody,
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
    svc: WorkflowService = Depends(_svc),
):
    return await svc.accept_detail(
        str(body.id),
        agent_id=str(actor.id),
        actor_name=_actor_display_name(actor) or getattr(actor, "name", None),
        actor_role=getattr(actor, "role", None),
        actor=actor,
        accepted=body.accepted,
        comment=body.comment,
    )
