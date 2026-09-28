from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaTask import TaskCreate, TaskUpdate, TaskResponse
from api.schemas.base import PaginatedResponse
from api.services import TaskService

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=Depends(require_roles("agent", "admin")),
    svc: TaskService = Depends(_svc),
):
    """M-02 — liste globale des tâches réservée au staff ; les citoyens n'ont pas accès."""
    return await svc.list_all(page=page, limit=limit)


_staff = Depends(require_roles("agent", "admin"))


@router.get("/pending", response_model=PaginatedResponse)
async def list_pending(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: TaskService = Depends(_svc),
):
    return await svc.list_pending(page=page, limit=limit)


@router.get("/by-request/{request_id}", response_model=PaginatedResponse)
async def list_by_request(
    request_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _=_staff,
    svc: TaskService = Depends(_svc),
):
    return await svc.list_by_request(request_id, page=page, limit=limit)


@router.get("/assigned-to/{agent_id}", response_model=PaginatedResponse)
async def list_assigned_to(
    agent_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: TaskService = Depends(_svc),
):
    return await svc.list_assigned_to(agent_id, page=page, limit=limit)


@router.get("/{id}", response_model=TaskResponse)
async def get_task(id: str, _=_staff, svc: TaskService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    _=Depends(require_roles("agent", "admin")),
    svc: TaskService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.put("/{id}", response_model=TaskResponse)
async def update_task(
    id: str,
    body: TaskUpdate,
    _=Depends(require_roles("agent", "admin")),
    svc: TaskService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.post("/{id}/complete", response_model=TaskResponse)
async def complete_task(
    id: str,
    resolution_note: Optional[str] = Query(None),
    _=Depends(require_roles("agent", "admin")),
    svc: TaskService = Depends(_svc),
):
    return await svc.complete(id, resolution_note=resolution_note)


@router.post("/{id}/reject", response_model=TaskResponse)
async def reject_task(
    id: str,
    rejection_reason: Optional[str] = Query(None),
    _=Depends(require_roles("admin")),
    svc: TaskService = Depends(_svc),
):
    return await svc.reject(id, rejection_reason=rejection_reason)


@router.post("/{id}/approve", response_model=TaskResponse)
async def approve_task(
    id: str,
    _=Depends(require_roles("admin")),
    svc: TaskService = Depends(_svc),
):
    return await svc.approve(id)


@router.post("/{id}/cancel", response_model=TaskResponse)
async def cancel_task(
    id: str,
    _=Depends(require_roles("agent", "admin")),
    svc: TaskService = Depends(_svc),
):
    return await svc.cancel(id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    id: str,
    _=Depends(require_roles("admin")),
    svc: TaskService = Depends(_svc),
):
    await svc.delete(id)
