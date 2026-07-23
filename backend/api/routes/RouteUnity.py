from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaUnity import UnityCreate, UnityUpdate, UnityResponse
from api.schemas.base import PaginatedResponse
from api.services.ServiceUnity import UnityService

router = APIRouter(
    prefix="/unities",
    tags=["unities"],
    dependencies=[Depends(get_current_user)],
)

_staff = Depends(require_roles("agent", "chief", "director", "admin"))


def _svc(db: AsyncSession = Depends(get_db)) -> UnityService:
    return UnityService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_unities(
    page: int = Query(1, ge=1),
    limit: int = Query(200, ge=1, le=500),
    svc: UnityService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/active", response_model=list[UnityResponse])
async def list_active_unities(svc: UnityService = Depends(_svc)):
    return await svc.list_active()


@router.get("/search", response_model=PaginatedResponse)
async def search_unities(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: UnityService = Depends(_svc),
):
    return await svc.search(q, page=page, limit=limit)


@router.get("/{id}", response_model=UnityResponse)
async def get_unity(id: str, svc: UnityService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=UnityResponse, status_code=status.HTTP_201_CREATED)
async def create_unity(
    body: UnityCreate,
    _=Depends(require_roles("admin")),
    svc: UnityService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.patch("/{id}", response_model=UnityResponse)
async def update_unity(
    id: str,
    body: UnityUpdate,
    _=Depends(require_roles("admin")),
    svc: UnityService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unity(
    id: str,
    _=Depends(require_roles("admin")),
    svc: UnityService = Depends(_svc),
):
    await svc.delete(id)
