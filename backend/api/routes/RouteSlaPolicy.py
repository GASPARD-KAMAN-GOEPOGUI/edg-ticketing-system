from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaSlaPolicy import SlaPolicyCreate, SlaPolicyUpdate, SlaPolicyResponse
from api.schemas.base import PaginatedResponse
from api.services import SlaPolicyService

# Lecture : agent, chief, director, admin (CDC §6.1 — affichage SLA sur les tickets)
read_router = APIRouter(
    prefix="/sla-policies",
    tags=["sla-policies"],
    dependencies=[Depends(require_roles("agent", "chief", "director", "admin"))],
)

# Écriture : admin uniquement
router = APIRouter(
    prefix="/sla-policies",
    tags=["sla-policies"],
    dependencies=[Depends(require_roles("admin"))],
)


def _svc(db: AsyncSession = Depends(get_db)) -> SlaPolicyService:
    return SlaPolicyService(db)


@read_router.get("/", response_model=PaginatedResponse)
async def list_policies(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: SlaPolicyService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@read_router.get("/active", response_model=list[SlaPolicyResponse])
async def list_active(svc: SlaPolicyService = Depends(_svc)):
    return await svc.list_active()


@read_router.get("/by-category/{category_id}", response_model=list[SlaPolicyResponse])
async def list_by_category(category_id: str, svc: SlaPolicyService = Depends(_svc)):
    return await svc.list_by_category(category_id)


@read_router.get("/find")
async def find_policy(
    category: str = Query(...),
    priority: str = Query(...),
    svc: SlaPolicyService = Depends(_svc),
):
    return await svc.find_policy(category, priority)


@read_router.get("/{id}", response_model=SlaPolicyResponse)
async def get_policy(id: str, svc: SlaPolicyService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=SlaPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(body: SlaPolicyCreate, svc: SlaPolicyService = Depends(_svc)):
    return await svc.create(body.dict())


@router.put("/{id}", response_model=SlaPolicyResponse)
async def update_policy(id: str, body: SlaPolicyUpdate, svc: SlaPolicyService = Depends(_svc)):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(id: str, svc: SlaPolicyService = Depends(_svc)):
    await svc.delete(id)
