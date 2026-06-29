from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaRequest import RequestCreate, RequestWorkflowCreate, RequestUpdate, RequestResponse, RequestSearch
from api.schemas.SchemaWorkflowDetail import WorkflowDetailResponse
from api.schemas.SchemaEscalation import EscalationResponse
from api.schemas.SchemaAttachment import AttachmentResponse
from pydantic import BaseModel
from api.schemas.base import PaginatedResponse
from api.services import RequestService, AttachmentService
from api.repositories import WorkflowDetailRepository, WorkflowRepository
from api.services.ServiceClamAV import scan_bytes as clamav_scan
from api.core.file_validator import validate_file_magic_bytes
from api import storage
from api.dependencies import get_current_user

router = APIRouter(
    prefix="/requests",
    tags=["requests"],
    dependencies=[Depends(get_current_user)],
)

public_router = APIRouter(prefix="/requests", tags=["requests-public"])

_ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "application/pdf",
}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 Mo
_MAX_FILES_PER_REQUEST = 5


async def _get_dir_unity_ids(db: AsyncSession, dir_unity_id: int) -> set[int]:
    """Retourne le set {direction + tous ses services} depuis l'organigramme (2 niveaux)."""
    from sqlalchemy import select as sa_select
    from api.models.ModelOrganigram import Organigram
    r1 = await db.execute(
        sa_select(Organigram.id)
        .where(Organigram.unity_id == dir_unity_id, Organigram.deleted_at.is_(None))
        .limit(1)
    )
    org_id = r1.scalar_one_or_none()
    ids: set[int] = {dir_unity_id}
    if org_id:
        r2 = await db.execute(
            sa_select(Organigram.unity_id)
            .where(Organigram.parent_id == org_id, Organigram.deleted_at.is_(None))
        )
        ids.update(uid for (uid,) in r2.all())
    return ids


def _check_request_access(actor, req, allowed_dir_unity_ids: set[int] | None = None) -> None:
    """
    Vérifie que l'acteur a le droit d'accéder à la demande `req`.
    Lève HTTP 403 si l'acteur est hors périmètre.

    Politique d'accès :
      user         → uniquement ses propres demandes
      agent/chief  → demandes de leur unité exacte
      director     → demandes de leur direction ET tous ses services (allowed_dir_unity_ids)
      dg / admin   → accès global
    """
    role = actor.role
    if role in ("dg", "admin"):
        return

    if role == "user":
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé : vous ne pouvez accéder qu'à vos propres demandes.",
            )
        return

    if role in ("agent", "chief"):
        if actor.unity_id and req.unity_id:
            if str(req.unity_id) == str(actor.unity_id):
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : cette demande n'est pas dans votre périmètre.",
        )

    if role == "director":
        if actor.unity_id and req.unity_id:
            ids = allowed_dir_unity_ids if allowed_dir_unity_ids else {actor.unity_id}
            if req.unity_id in ids:
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : cette demande n'est pas dans votre direction.",
        )


async def _resolve_access(actor, req, db: AsyncSession) -> None:
    """Wrapper async : pré-calcule les unity_ids autorisés pour un directeur puis vérifie l'accès."""
    dir_ids = None
    if actor.role == "director" and actor.unity_id:
        dir_ids = await _get_dir_unity_ids(db, actor.unity_id)
    _check_request_access(actor, req, dir_ids)


def _svc(db: AsyncSession = Depends(get_db)) -> RequestService:
    return RequestService(db)


def _detail_repo(db: AsyncSession = Depends(get_db)) -> WorkflowDetailRepository:
    return WorkflowDetailRepository(db)


def _wf_repo(db: AsyncSession = Depends(get_db)) -> WorkflowRepository:
    return WorkflowRepository(db)


def _att_svc(db: AsyncSession = Depends(get_db)) -> AttachmentService:
    return AttachmentService(db)


# ── Listes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedResponse)
async def list_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=1000),
    request_status: Optional[str] = Query(None),
    is_external: Optional[bool] = Query(None),
    direction_id: Optional[str] = Query(None),
    unit_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    requester_id: Optional[str] = Query(None),
    sla_breached: Optional[bool] = Query(None),
    in_triage: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, min_length=1),
    date_from: Optional[str] = Query(None, description="Date de début ISO (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Date de fin ISO (YYYY-MM-DD)"),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Liste filtrée et paginée — visibilité restreinte au périmètre de l'utilisateur."""
    # Vue personnelle : l'acteur demande SES propres demandes en tant que requester.
    # Dans ce cas, on bypasse le forcing unit_id/direction_id pour tous les rôles.
    is_own_view = requester_id is not None and requester_id == str(actor.id)

    # Filtrage RBAC — forcé, le client ne peut pas étendre son périmètre (C-N°3)
    if is_own_view:
        pass  # requester_id = actor.id suffit ; unit/direction non forcés
    elif actor.role == "user":
        requester_id = str(actor.id)           # toujours ses propres demandes
    elif actor.role in ("agent", "chief"):
        if actor.unity_id:
            unit_id = str(actor.unity_id)       # forcé, ignore le paramètre client
            direction_id = None
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une unité. Contactez un administrateur.",
            )
    elif actor.role == "director":
        if actor.unity_id:
            direction_id = str(actor.unity_id)  # forcé
            unit_id = None
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une direction. Contactez un administrateur.",
            )
    # dg, admin : visibilité globale — filtres client acceptés

    has_filter = any(v is not None for v in [
        request_status, is_external, direction_id, unit_id,
        assignee_id, requester_id, sla_breached, in_triage, search,
        date_from, date_to,
    ])
    if has_filter:
        return await svc.list_filtered(
            request_status=request_status,
            is_external=is_external,
            direction_id=direction_id,
            unit_id=unit_id,
            assignee_id=assignee_id,
            requester_id=requester_id,
            sla_breached=sla_breached,
            in_triage=in_triage,
            search=search,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
    return await svc.list_all(page=page, limit=limit)


_staff = Depends(require_roles("agent", "chief", "director", "dg", "admin"))


@router.get("/triage", response_model=PaginatedResponse)
async def list_triage(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_pending_triage(page=page, limit=limit)


@router.get("/sla-breached", response_model=PaginatedResponse)
async def list_sla_breached(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_sla_breached(page=page, limit=limit)


@router.get("/stats/by-status")
async def stats_by_status(_=_staff, svc: RequestService = Depends(_svc)):
    return await svc.count_by_status()


@router.get("/search", response_model=PaginatedResponse)
async def search_requests(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    # Les utilisateurs standard ne recherchent que dans leurs propres demandes
    if actor.role == "user":
        return await svc.list_filtered(requester_id=str(actor.id), search=q, page=page, limit=limit)
    return await svc.search(q, page=page, limit=limit)


@public_router.get("/track", response_model=RequestResponse)
async def track_request(
    ref: str = Query(..., description="Référence EDG-XXXX-XXXX"),
    email: Optional[str] = Query(None, description="Email associé au compte demandeur"),
    phone: Optional[str] = Query(None, description="Téléphone associé au compte demandeur"),
    svc: RequestService = Depends(_svc),
):
    """Suivi public — nécessite ref + (email ou téléphone) du compte ayant créé la demande."""
    return await svc.track(ref.strip().upper(), email=email, phone=phone)


@router.get("/queue", response_model=PaginatedResponse)
async def list_queue(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    direction_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    request_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, min_length=1),
    actor=Depends(require_roles("agent", "chief", "director", "dg", "admin")),
    svc: RequestService = Depends(_svc),
):
    """File d'attente active — réservée aux agents et supérieurs, filtrée par périmètre."""
    # Forçage RBAC — le paramètre client direction_id est ignoré (C-N°3)
    if actor.role in ("agent", "chief", "director"):
        direction_id = str(actor.unity_id) if actor.unity_id else None
    return await svc.list_queue(
        direction_id=direction_id,
        assignee_id=assignee_id,
        priority=priority,
        request_status=request_status,
        search=search,
        page=page,
        limit=limit,
    )


class QualifyTriageBody(BaseModel):
    category: str
    priority: str
    direction_id: str
    unit_id: Optional[str] = None


@router.post("/{id}/qualify", response_model=RequestResponse)
async def qualify_triage(
    id: str,
    body: QualifyTriageBody,
    actor=Depends(require_roles("agent", "chief", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Qualifie une demande de triage — réservé agent, chief, admin."""
    return await svc.qualify_triage(id, body.dict(exclude_none=True), actor_id=str(actor.id))


@router.get("/by-status/{request_status}", response_model=PaginatedResponse)
async def list_by_status(
    request_status: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_by_status(request_status, page=page, limit=limit)


@router.get("/by-assignee/{assignee_id}", response_model=PaginatedResponse)
async def list_by_assignee(
    assignee_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_by_assignee(assignee_id, page=page, limit=limit)


@router.get("/by-requester/{requester_id}", response_model=PaginatedResponse)
async def list_by_requester(
    requester_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    if actor.role == "user" and str(actor.id) != requester_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé aux demandes d'un autre utilisateur.",
        )
    return await svc.list_by_requester(requester_id, page=page, limit=limit)


@router.get("/by-direction/{direction_id}", response_model=PaginatedResponse)
async def list_by_direction(
    direction_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_by_direction(direction_id, page=page, limit=limit)


@router.get("/by-unit/{unit_id}", response_model=PaginatedResponse)
async def list_by_unit(
    unit_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    """Requêtes d'une unité spécifique."""
    return await svc.list_by_unit(unit_id, page=page, limit=limit)


@router.get("/ref/{ref}", response_model=RequestResponse)
async def get_by_ref(
    ref: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """H-07 — ownership check : un user ne voit que ses propres demandes."""
    req = await svc.get_by_ref(ref)
    if actor.role == "user" and str(req.requester_id) != str(actor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette demande.",
        )
    return svc._decrypt_schema(RequestResponse.from_orm(req))


@router.get("/{id}", response_model=RequestResponse)
async def get_request(
    id: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """H-07 — ownership check : un user ne voit que ses propres demandes."""
    req = await svc.get_by_id(id)
    if actor.role == "user" and str(req.requester_id) != str(actor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette demande.",
        )
    return svc._decrypt_schema(RequestResponse.from_orm(req))


# ── Premier résultat filtré (pattern edgrh GET /items/) ───────────────────────

@router.get(
    "/items/",
    response_model=RequestResponse,
    summary="Premier résultat filtré — pattern edgrh get_items()",
    description=(
        "Retourne LA PREMIÈRE demande correspondant aux critères. "
        "Utilisez GET / pour une liste paginée, GET /search pour la recherche textuelle."
    ),
)
async def get_request_item(
    params: RequestSearch = Depends(),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    return await svc.get_first_filtered(
        request_status=params.request_status,
        unity_id=str(params.unity_id) if params.unity_id else None,
        assignee_id=str(params.assignee_id) if params.assignee_id else None,
        requester_id=str(params.requester_id) if params.requester_id else None,
        is_external=params.is_external,
        in_triage=params.in_triage,
        sla_breached=params.sla_breached,
        priority=params.priority,
    )


# ── Créations ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: RequestWorkflowCreate,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """C-02 — requester_id forcé depuis le JWT.
    Supporte workflows:[] pour créer le circuit de validation en même temps que la demande
    (pattern edgrh POST /demand/workflow avec DemandWorkflowCreateSchema)."""
    data = body.dict()
    data["requester_id"] = actor.id
    data["requester_role"] = str(actor.role)
    obj = await svc.create(data)
    return svc._decrypt_schema(RequestResponse.from_orm(obj))


# ── Modifications ─────────────────────────────────────────────────────────────

@router.patch("/{id}", response_model=RequestResponse)
async def update_request(
    id: str,
    body: RequestUpdate,
    actor=Depends(require_roles("user", "agent", "chief", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    data = body.dict(exclude_unset=True)
    if actor.role == "user":
        # Un utilisateur ne peut modifier que ses propres demandes (titre + description)
        req = await svc.get_by_id(id)
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(status_code=403, detail="Vous ne pouvez modifier que vos propres demandes.")
        allowed = {"title", "description"}
        data = {k: v for k, v in data.items() if k in allowed}
    return await svc.update(id, data, actor_id=str(actor.id))


class RequesterEditBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    direction_id: Optional[int] = None
    unit_id: Optional[int] = None
    unity_id: Optional[int] = None


@router.patch("/{id}/requester-edit", response_model=RequestResponse)
async def requester_edit(
    id: str,
    body: RequesterEditBody,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Modification complète par le demandeur — uniquement si status=new et aucun acteur n'est intervenu.
    Ouvert à tous les rôles : le service valide que l'acteur est bien le demandeur du ticket (C-02)."""
    return await svc.requester_edit(
        id,
        body.dict(exclude_none=True),
        actor_id=str(actor.id),
        actor_role=str(actor.role),
    )


@router.post("/{id}/assign", response_model=RequestResponse)
async def assign_request(
    id: str,
    assignee_id: str = Query(...),
    actor=Depends(require_roles("agent", "chief", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Assignation d'une demande — DG interdit (rôles autorisés : agent, chief, admin)."""
    return await svc.assign(id, assignee_id, actor_id=str(actor.id))


@router.post("/{id}/resolve", response_model=RequestResponse)
async def resolve_request(
    id: str,
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Résolution — réservé agent, chef, directeur, admin."""
    return await svc.resolve(id, actor_id=str(actor.id))


@router.post("/{id}/close", response_model=RequestResponse)
async def close_request(
    id: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Clôture — demandeur (ses propres tickets résolus) ou agent/chef/directeur/admin."""
    if actor.role == "user":
        req = await svc.get_by_id(id)
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez clôturer que vos propres demandes.",
            )
        if req.request_status not in ("resolved",):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vous pouvez clôturer uniquement une demande à l'état 'resolved'.",
            )
    elif actor.role not in ("agent", "chief", "director", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")
    return await svc.close(id, actor_id=str(actor.id))


class ReopenRequestBody(BaseModel):
    reason: str
    actor_name: Optional[str] = None


@router.post("/{id}/request-reopen", response_model=RequestResponse, status_code=status.HTTP_200_OK)
async def user_request_reopen(
    id: str,
    body: ReopenRequestBody,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """
    Phase 1 — L'utilisateur refuse la résolution et demande la réouverture.
    Réservé au demandeur propriétaire du ticket. Motif obligatoire.
    """
    req = await svc.get_by_id(id)
    if req.requester_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez demander la réouverture que de vos propres tickets.",
        )
    return await svc.request_reopen(
        id,
        actor_id=str(actor.id),
        actor_name=body.actor_name or actor.name,
        reason=body.reason,
    )


@router.post("/{id}/reopen", response_model=RequestResponse)
async def reopen_request(
    id: str,
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Phase 2 — Le chef approuve la réouverture (change le statut en REOPENED)."""
    return await svc.reopen(id, actor_id=str(actor.id), actor_name=getattr(actor, "name", None))


@router.post("/{id}/cancel", response_model=RequestResponse)
async def cancel_request(
    id: str,
    reason: Optional[str] = Query(None),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Annulation — demandeur (ses propres tickets) ou agent/chief/admin."""
    if actor.role == "user":
        req = await svc.get_by_id(id)
        if req.requester_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez annuler que vos propres demandes.",
            )
    elif actor.role not in ("agent", "chief", "director", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")
    return await svc.cancel(id, actor_id=str(actor.id), reason=reason)


class RejectBody(BaseModel):
    reason: str


@router.post("/{id}/reject", response_model=RequestResponse)
async def reject_request(
    id: str,
    body: RejectBody,
    actor=Depends(require_roles("chief", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Rejet d'un ticket par le chef de service — motif obligatoire."""
    return await svc.reject(
        id,
        actor_id=str(actor.id),
        actor_name=getattr(actor, "name", None),
        reason=body.reason,
    )


class ReassignBody(BaseModel):
    target_unity_id: str
    reason: Optional[str] = None


@router.post("/{id}/reassign", response_model=RequestResponse)
async def reassign_request(
    id: str,
    body: ReassignBody,
    actor=Depends(require_roles("chief", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Réaffectation d'un ticket à un autre service."""
    return await svc.reassign_service(
        id,
        body.target_unity_id,
        actor_id=str(actor.id),
        actor_name=getattr(actor, "name", None),
        reason=body.reason,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_request(
    id: str,
    _=Depends(require_roles("admin")),
    svc: RequestService = Depends(_svc),
):
    await svc.delete(id)


# ── Escalade ──────────────────────────────────────────────────────────────────

class EscalateBody(BaseModel):
    level: str
    reason: str
    from_agent_name: str = ""
    to_agent_name: str = ""
    from_user_id: Optional[str] = None
    to_user_id: Optional[str] = None
    sla_over_hours: int = 0


@router.post("/{id}/escalate", response_model=EscalationResponse, status_code=status.HTTP_201_CREATED)
async def escalate_request(
    id: str,
    body: EscalateBody,
    actor=Depends(require_roles("agent", "chief", "director", "admin")),
    svc: RequestService = Depends(_svc),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
):
    """Escalade d'une demande — enregistrée comme événement workflow_detail (event_type='escalation_manual')."""
    actor_id = str(actor.id)
    req = await svc.get_by_id(id)
    wf = await wf_repo.find_active_workflow(id)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun workflow actif pour cette demande — impossible d'escalader.",
        )
    event = await detail_repo.create_event({
        "workflow_id": str(wf.id),
        "event_type": "escalation_manual",
        "label": f"Escalade {body.level} — {req.ref}",
        "actor_id": body.from_user_id or actor_id,
        "actor_name": body.from_agent_name or actor.name,
        "comment": body.reason,
        "activated": True,
        "infos": {
            "level": body.level,
            "to_user_id": body.to_user_id,
            "to_agent_name": body.to_agent_name,
            "sla_over_hours": body.sla_over_hours,
            "priority": req.priority,
            "status": "open",
        },
    })
    await svc.update(id, {"request_status": "escalated"}, actor_id=actor_id)

    if body.to_user_id:
        from api.services.NotificationEmitter import emit as emit_notif
        await emit_notif(
            svc.session,
            recipient_id=body.to_user_id,
            title=f"Escalade {body.level} — {req.ref}",
            body=f"La demande {req.ref} a été escaladée par {body.from_agent_name or actor.name} : {body.reason[:100]}",
            type="warning",
            request_id=str(req.id),
            action_label="Voir la demande",
            action_url=f"/app/requests/{req.id}",
        )

    return EscalationResponse.from_detail(event, int(req.id), req.ref)


# ── Comments (nested — stockés dans workflow_detail, event_type='comment') ───

class _CommentBody(BaseModel):
    body: str
    is_public: bool = False


@router.get("/{request_id}/comments", response_model=list[WorkflowDetailResponse])
async def list_comments(
    request_id: str,
    public_only: bool = Query(False),
    actor=Depends(get_current_user),
    repo: WorkflowDetailRepository = Depends(_detail_repo),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """C-05 — liste les événements event_type='comment' du workflow de la demande.
    Un citoyen (role=user) ne voit que les commentaires publics (is_public=True dans infos)."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    if actor.role == "user":
        public_only = True
    return await repo.list_comments_by_request(request_id, public_only=public_only)


@router.post("/{request_id}/comments", response_model=WorkflowDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    request_id: str,
    body: _CommentBody,
    actor=Depends(get_current_user),
    req_svc: RequestService = Depends(_svc),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
    db: AsyncSession = Depends(get_db),
):
    """C-05 — author_id et author_name forcés depuis le JWT.
    Crée un événement event_type='comment' dans le workflow_detail de la demande."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    wf = await wf_repo.find_active_workflow(request_id)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun workflow actif pour cette demande.",
        )
    event = await detail_repo.create_event({
        "workflow_id": str(wf.id),
        "event_type": "comment_added",
        "label": body.body[:500],
        "actor_id": actor.id,
        "actor_name": actor.name,
        "comment": body.body,
        "infos": {"is_public": body.is_public},
    })

    # Notifier l'agent assigné quand l'utilisateur répond à une demande en attente
    if actor.role == "user" and req.request_status in ("pending", "waiting_user"):
        assignee_id = getattr(req, "assignee_id", None)
        if assignee_id:
            from api.services.NotificationEmitter import emit as emit_notif
            await emit_notif(
                db,
                recipient_id=str(assignee_id),
                title="Réponse reçue du demandeur",
                body=f"Le demandeur a répondu à votre demande d'informations sur la demande {req.ref}.",
                type="info",
                request_id=request_id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{request_id}",
            )

    return event


@router.delete("/{request_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    request_id: str,
    comment_id: str,
    actor=Depends(get_current_user),
    req_svc: RequestService = Depends(_svc),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    db: AsyncSession = Depends(get_db),
):
    """C-05 — ownership : un user ne peut supprimer que ses propres commentaires."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    entry = await detail_repo.get_by_id(comment_id)
    if entry is None or entry.event_type != "comment_added":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commentaire introuvable.")
    if actor.role == "user" and str(entry.agent_id) != str(actor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez supprimer que vos propres commentaires.",
        )
    await detail_repo.delete(comment_id)


# ── Timeline (nested) ─────────────────────────────────────────────────────────

@router.get("/{request_id}/timeline", response_model=list[WorkflowDetailResponse])
async def list_timeline(
    request_id: str,
    actor=Depends(get_current_user),
    repo: WorkflowDetailRepository = Depends(_detail_repo),
    svc: RequestService = Depends(_svc),
):
    req = await svc.get_by_id(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    _check_request_access(actor, req)
    return await repo.list_by_request(request_id)


class _TimelineEventBody(BaseModel):
    event_type: str
    label: str


@router.post("/{request_id}/timeline", response_model=WorkflowDetailResponse, status_code=status.HTTP_201_CREATED)
async def add_timeline_event(
    request_id: str,
    body: _TimelineEventBody,
    actor=Depends(require_roles("agent", "chief", "director", "dg", "admin")),
    repo: WorkflowDetailRepository = Depends(_detail_repo),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
):
    """C-06 — injection de timeline réservée au staff (pas les citoyens)."""
    wf = await wf_repo.find_active_workflow(request_id)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun workflow actif pour cette demande.",
        )
    return await repo.create_event({
        "workflow_id": str(wf.id),
        "event_type": body.event_type,
        "label": body.label,
        "actor_id": actor.id,
        "actor_name": actor.name,
    })


# ── Pièces jointes (nested) ───────────────────────────────────────────────────

@router.get("/{request_id}/attachments", response_model=List[AttachmentResponse])
async def list_attachments(
    request_id: str,
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_att_svc),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """C-N°4 — ownership check avant de lister les pièces jointes."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    result = await svc.list_by_request(request_id, page=1, limit=100)
    items = result.items if hasattr(result, "items") else []
    for item in items:
        item.storage_path = storage.presigned_url(item.storage_path)
    return items


@router.post(
    "/{request_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    request_id: str,
    file: UploadFile = File(...),
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_att_svc),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload une pièce jointe (multipart/form-data).
    Contraintes : jpg/png/webp/pdf · max 10 Mo · max 5 par demande.

    Sécurité :
      C-04  — uploader_id forcé depuis JWT
      C-N°1 — validation par magic bytes (Content-Type client ignoré)
      C-N°2 — scan ClamAV avant sauvegarde (si CLAMAV_ENABLED=True)
      C-N°4 — ownership check : seuls les acteurs dans le périmètre peuvent uploader
    """
    # C-N°4 — vérifier que l'acteur a accès à cette demande
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)

    # Lire les données brutes (nécessaire pour magic bytes + ClamAV)
    data = await file.read()

    # C-N°1 — validation par magic bytes ; lève HTTP 422 si invalide / spoofé
    declared_mime = file.content_type or "application/octet-stream"
    if declared_mime not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=422,
            detail=f"Type de fichier non autorisé : {declared_mime}. Autorisés : jpeg, png, webp, pdf.",
        )
    real_mime = validate_file_magic_bytes(data, declared_mime)

    # Valider la taille
    if len(data) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Fichier trop volumineux ({len(data) // 1024} Ko). Maximum : 10 Mo.",
        )

    # Vérifier le nombre de fichiers existants
    existing = await svc.list_by_request(request_id, page=1, limit=100)
    count = existing.total if hasattr(existing, "total") else 0
    if count >= _MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {_MAX_FILES_PER_REQUEST} pièces jointes par demande.",
        )

    # C-N°2 — scan antivirus ClamAV
    scan_result = await clamav_scan(data)
    if scan_result.status == "infected":
        raise HTTPException(
            status_code=422,
            detail=f"Fichier rejeté — menace détectée : {scan_result.threat_name}.",
        )
    scan_db_status = scan_result.status  # "clean" | "scan_error"

    # Sauvegarder (storage_path généré côté serveur — jamais fourni par le client)
    storage_path, _ = storage.save_file(data, file.filename or "fichier", request_id)

    att = await svc.create({
        "request_id": request_id,
        "uploader_id": actor.id,       # C-04 — forcé depuis JWT
        "filename": file.filename or "fichier",
        "storage_path": storage_path,
        "mime_type": real_mime,        # C-N°1 — MIME validé par magic bytes
        "size_bytes": len(data),
        "scan_status": scan_db_status, # C-N°2 — résultat ClamAV
    })

    att.storage_path = storage.presigned_url(storage_path)
    return att


@router.delete("/{request_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    request_id: str,
    attachment_id: str,
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_att_svc),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """C-N°4 — ownership check avant suppression d'une pièce jointe."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    att = await svc.get_by_id(attachment_id)
    if att and str(att.request_id) == str(request_id):
        storage.delete_file(att.storage_path)
    await svc.delete(attachment_id)


# ── Téléchargement fichiers locaux ────────────────────────────────────────────

@router.get("/download/{path:path}")
async def download_file(
    path: str,
    actor=Depends(get_current_user),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """
    Sert les fichiers uploadés localement.
    C-N°4 — ownership check : extrait request_id depuis le chemin de stockage
    (format : requests/{request_id}/{uuid}_{filename}).
    """
    # Empêcher la traversée de répertoires
    uploads_dir = Path(__file__).parent.parent.parent / "uploads"
    full = (uploads_dir / path).resolve()
    if not str(full).startswith(str(uploads_dir.resolve())):
        raise HTTPException(status_code=400, detail="Chemin invalide.")
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")

    # Extraire request_id depuis le chemin stocké (requests/<id>/...)
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "requests":
        request_id_from_path = parts[1]
        try:
            req = await req_svc.get_by_id(request_id_from_path)
            await _resolve_access(actor, req, db)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=403, detail="Accès refusé à ce fichier.")
    # Si le chemin ne correspond pas au format attendu, refuser par défaut
    elif actor.role not in ("dg", "admin"):
        raise HTTPException(status_code=403, detail="Accès refusé à ce fichier.")

    return FileResponse(str(full))


# ── Fusion de tickets ──────────────────────────────────────────────────────────

class _MergeBody(BaseModel):
    target_id: str


@router.post(
    "/{id}/merge",
    response_model=RequestResponse,
    dependencies=[Depends(require_roles("agent", "chief", "admin"))],
)
async def merge_request(
    id: str,
    body: _MergeBody,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """
    Fusionne la demande {id} (source) dans la demande body.target_id (cible).
    La demande source est annulée et marquée merged_into_id = target.id.
    Retourne la demande cible mise à jour.
    """
    return await svc.merge(id, body.target_id, actor_id=str(actor.id))


# ── Duplication de ticket ──────────────────────────────────────────────────────

@router.post(
    "/{id}/duplicate",
    response_model=RequestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("agent", "chief", "admin"))],
)
async def duplicate_request(
    id: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """
    Crée une copie de la demande {id} avec une nouvelle référence et le statut 'new'.
    L'assignee et le champ merged_into_id ne sont pas copiés.
    """
    return await svc.duplicate(id, actor_id=str(actor.id))


# ── Suppression avec vérification UUID (pattern edgrh DELETE /{id}/{uuid}) ────

@router.delete(
    "/{id}/{uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Suppression avec vérification UUID — pattern edgrh delete_uuid()",
    description="Double vérification id + uuid avant soft-delete. Réservé admin.",
)
async def delete_request_uuid(
    id: str,
    uuid: str,
    _=Depends(require_roles("admin")),
    svc: RequestService = Depends(_svc),
):
    await svc.delete_by_uuid(id, uuid)


# ── Restauration soft-delete (pattern edgrh PUT /restore/{id}) ────────────────

@router.put(
    "/{id}/restore",
    response_model=RequestResponse,
    summary="Restaurer une demande soft-deleted — pattern edgrh /restore/{id}",
)
async def restore_request(
    id: str,
    _=Depends(require_roles("admin")),
    svc: RequestService = Depends(_svc),
):
    return await svc.restore(id)
