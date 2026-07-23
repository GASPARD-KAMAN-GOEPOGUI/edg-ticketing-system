from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.core.rbac import normalize_role
from api.schemas.SchemaAnnouncement import (
    AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
)
from api.schemas.SchemaAnnouncementTargetRole import AnnouncementTargetRoleResponse
from api.schemas.base import PaginatedResponse
from api.services import AnnouncementService

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"],
    dependencies=[Depends(get_current_user)],
)

_editor = Depends(require_roles("admin"))
_ADMIN_ROLES = {"admin"}
_TEAM_MSG_ROLES = {"admin", "chief"}


def _svc(db: AsyncSession = Depends(get_db)) -> AnnouncementService:
    return AnnouncementService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_announcements(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.list_all(actor_role=actor.role, page=page, limit=limit)


@router.get("/published", response_model=PaginatedResponse)
async def list_published(
    audience: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.list_published(actor_role=actor.role, audience=audience, page=page, limit=limit)


# Doit être AVANT /{id} pour éviter les conflits de matching FastAPI
@router.get("/active-alerts", response_model=PaginatedResponse)
async def list_active_alerts(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
    actor=Depends(get_current_user),
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.list_active_alerts(actor_role=actor.role, page=page, limit=limit)


@router.get("/active/{audience}", response_model=PaginatedResponse)
async def list_active_for_audience(
    audience: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.list_active_for_audience(audience, actor_role=actor.role, page=page, limit=limit)


@router.get("/by-author/{author_id}", response_model=PaginatedResponse)
async def list_by_author(
    author_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.list_by_author(author_id, actor_role=actor.role, page=page, limit=limit)


@router.get("/search", response_model=PaginatedResponse)
async def search_announcements(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.search(q, actor_role=actor.role, page=page, limit=limit)


@router.get("/{id}", response_model=AnnouncementResponse)
async def get_announcement(
    id: str,
    actor=Depends(get_current_user),
    svc: AnnouncementService = Depends(_svc),
):
    ann = await svc.get_by_id(id)
    if ann.visibility == "admin_only" and normalize_role(actor.role) not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette annonce.",
        )
    return ann


@router.post("/team-message", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_team_message(
    body: AnnouncementCreate,
    actor=Depends(require_roles("admin", "chief")),
    svc: AnnouncementService = Depends(_svc),
):
    """Chef : publie un message d'équipe visible uniquement par son service (audience=unit)."""
    data = body.dict()
    if actor.role == "chief":
        data["audience"] = "unit"
        data["announcement_status"] = "published"
        # Restreindre à son unité uniquement
        data.setdefault("infos", {})
        if isinstance(data.get("infos"), dict):
            data["infos"]["target_unit_id"] = str(actor.unit_id) if actor.unit_id else None
    return await svc.create(data)


@router.post("/", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    body: AnnouncementCreate,
    _actor=_editor,
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.patch("/{id}", response_model=AnnouncementResponse)
async def update_announcement(
    id: str,
    body: AnnouncementUpdate,
    _actor=_editor,
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.post("/{id}/publish", response_model=AnnouncementResponse)
async def publish_announcement(id: str, _actor=_editor, svc: AnnouncementService = Depends(_svc)):
    return await svc.publish(id)


@router.post("/{id}/close", response_model=AnnouncementResponse)
async def close_announcement(id: str, _actor=_editor, svc: AnnouncementService = Depends(_svc)):
    return await svc.close(id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(id: str, _actor=_editor, svc: AnnouncementService = Depends(_svc)):
    await svc.delete(id)


# ── Target roles ──────────────────────────────────────────────────────────────

@router.get("/{id}/target-roles", response_model=list[AnnouncementTargetRoleResponse])
async def list_target_roles(id: str, svc: AnnouncementService = Depends(_svc)):
    return await svc.list_target_roles(id)


@router.put("/{id}/target-roles", response_model=list[AnnouncementTargetRoleResponse])
async def set_target_roles(
    id: str,
    _actor=_editor,
    roles: list[str] | None = Body(default=None),
    svc: AnnouncementService = Depends(_svc),
):
    return await svc.set_target_roles(id, roles or [])


