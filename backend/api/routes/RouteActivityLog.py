from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_roles
from api.schemas.SchemaActivityLog import ActivityLogCreate, ActivityLogResponse
from api.schemas.base import PaginatedResponse
from api.services import ActivityLogService

router = APIRouter(
    prefix="/activity-logs",
    tags=["activity-logs"],
    dependencies=[Depends(require_roles("admin", "dg"))],
)


def _svc(db: AsyncSession = Depends(get_db)) -> ActivityLogService:
    return ActivityLogService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: ActivityLogService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/errors", response_model=PaginatedResponse)
async def list_errors(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: ActivityLogService = Depends(_svc),
):
    return await svc.list_errors(page=page, limit=limit)


@router.get("/by-actor/{actor_id}", response_model=PaginatedResponse)
async def list_by_actor(
    actor_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: ActivityLogService = Depends(_svc),
):
    return await svc.list_by_actor(actor_id, page=page, limit=limit)


@router.get("/search", response_model=PaginatedResponse)
async def search_logs(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: ActivityLogService = Depends(_svc),
):
    return await svc.search(q, page=page, limit=limit)


@router.get("/{id}", response_model=ActivityLogResponse)
async def get_log(id: str, svc: ActivityLogService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=ActivityLogResponse, status_code=status.HTTP_201_CREATED)
async def append_log(body: ActivityLogCreate, svc: ActivityLogService = Depends(_svc)):
    return await svc.append(body.dict())
