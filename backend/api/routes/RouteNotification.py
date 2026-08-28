from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.core.rbac import normalize_role
from api.schemas.SchemaNotification import NotificationCreate, NotificationResponse
from api.schemas.base import PaginatedResponse
from api.services import NotificationService, RequestService

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


def _req_svc(db: AsyncSession = Depends(get_db)) -> RequestService:
    return RequestService(db)


def _check_recipient_access(actor, recipient_id: str) -> None:
    """Vérifie que l'utilisateur accède uniquement à ses propres notifications."""
    if str(actor.id) != recipient_id and normalize_role(actor.role) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé aux notifications d'un autre utilisateur.",
        )


# ── Endpoints spec §4.9 ───────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedResponse)
async def list_notifications(
    unread: bool = Query(False, alias="unread"),
    nature: Optional[str] = Query(None, description="annonce | demande"),
    archived: bool = Query(False, description="Notifications archivées (masquées, jamais supprimées)"),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    """Notifications de l'utilisateur connecté — ID extrait du JWT."""
    return await svc.list_mine(
        str(actor.id),
        actor_role=actor.role,
        unread_only=unread,
        nature=nature,
        archived=archived,
        page=page,
        limit=limit,
    )


@router.put("/{id}/read", response_model=NotificationResponse)
async def mark_as_read(
    id: str,
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    notif = await svc.get_by_id(id)
    _check_recipient_access(actor, str(notif.recipient_id))
    return await svc.mark_as_read(id)


@router.post("/read-all")
async def mark_all_read(
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    """Marque toutes les notifications de l'utilisateur connecté comme lues."""
    count = await svc.mark_all_read(str(actor.id))
    return {"updated": count}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    id: str,
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    """Archive la notification (deleted_at) — jamais de suppression physique, récupérable via /restore."""
    notif = await svc.get_by_id(id)
    _check_recipient_access(actor, str(notif.recipient_id))
    await svc.delete(id)


@router.post("/{id}/restore", response_model=NotificationResponse)
async def restore_notification(
    id: str,
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    """Restaure une notification archivée dans la vue active de l'utilisateur."""
    notif = await svc.get_by_id(id, include_deleted=True)
    _check_recipient_access(actor, str(notif.recipient_id))
    return await svc.restore(id)


# ── Endpoints backward-compat ─────────────────────────────────────────────────

@router.get("/by-recipient/{recipient_id}", response_model=PaginatedResponse)
async def list_by_recipient(
    recipient_id: str,
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    _check_recipient_access(actor, recipient_id)
    return await svc.list_by_recipient(
        recipient_id,
        actor_role=actor.role,
        unread_only=unread_only,
        page=page,
        limit=limit,
    )


@router.get("/by-recipient/{recipient_id}/unread-count")
async def count_unread(
    recipient_id: str,
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    _check_recipient_access(actor, recipient_id)
    count = await svc.count_unread(recipient_id, actor_role=actor.role)
    return {"unread": count}


@router.get("/by-request/{request_id}", response_model=PaginatedResponse)
async def list_by_request(
    request_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    role = normalize_role(actor.role)
    if role == "user":
        req = await req_svc.get_by_id(request_id)
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé aux notifications de cette demande.",
            )
    elif role not in ("agent-support", "chief-service", "chief-departement", "director", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")
    return await svc.list_by_request(request_id, page=page, limit=limit)


@router.get("/{id}", response_model=NotificationResponse)
async def get_notification(
    id: str,
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    notif = await svc.get_by_id(id)
    _check_recipient_access(actor, str(notif.recipient_id))
    return notif


@router.post("/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    _=Depends(require_roles("admin")),
    svc: NotificationService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.post("/{id}/read-legacy", response_model=NotificationResponse)
async def mark_as_read_legacy(
    id: str,
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    notif = await svc.get_by_id(id)
    _check_recipient_access(actor, str(notif.recipient_id))
    return await svc.mark_as_read(id)


@router.post("/by-recipient/{recipient_id}/read-all")
async def mark_all_read_legacy(
    recipient_id: str,
    actor=Depends(get_current_user),
    svc: NotificationService = Depends(_svc),
):
    _check_recipient_access(actor, recipient_id)
    count = await svc.mark_all_read(recipient_id)
    return {"updated": count}
