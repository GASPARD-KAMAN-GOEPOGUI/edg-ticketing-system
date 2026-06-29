from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaRoutingRule import RoutingRuleCreate, RoutingRuleUpdate, RoutingRuleResponse
from api.schemas.base import PaginatedResponse
from api.services import RoutingRuleService

router = APIRouter(
    prefix="/routing-rules",
    tags=["routing-rules"],
    dependencies=[Depends(require_roles("admin"))],
)

# Router lisible par les directeurs (lecture + CRUD restreint à leur direction)
director_router = APIRouter(
    prefix="/routing-rules",
    tags=["routing-rules"],
    dependencies=[Depends(require_roles("admin", "director"))],
)


def _svc(db: AsyncSession = Depends(get_db)) -> RoutingRuleService:
    return RoutingRuleService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_rules(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: RoutingRuleService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/auto-assign", response_model=list[RoutingRuleResponse])
async def list_auto_assign(svc: RoutingRuleService = Depends(_svc)):
    return await svc.list_auto_assign()


@router.get("/by-direction/{direction_id}", response_model=list[RoutingRuleResponse])
async def list_by_direction(direction_id: str, svc: RoutingRuleService = Depends(_svc)):
    return await svc.list_by_direction(direction_id)


@router.get("/{id}", response_model=RoutingRuleResponse)
async def get_rule(id: str, svc: RoutingRuleService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=RoutingRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(body: RoutingRuleCreate, svc: RoutingRuleService = Depends(_svc)):
    return await svc.create(body.dict())


@router.patch("/{id}", response_model=RoutingRuleResponse)
async def update_rule(id: str, body: RoutingRuleUpdate, svc: RoutingRuleService = Depends(_svc)):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(id: str, svc: RoutingRuleService = Depends(_svc)):
    await svc.delete(id)


# ── Endpoints directeur (lecture + CRUD restreint à leur direction) ───────────

@director_router.get("/by-direction/{direction_id}", response_model=list[RoutingRuleResponse])
async def list_director_rules(
    direction_id: str,
    actor=Depends(get_current_user),
    svc: RoutingRuleService = Depends(_svc),
):
    """Directeur : liste les règles qui ciblent SA direction uniquement."""
    if actor.role == "director" and str(actor.direction_id) != direction_id:
        raise HTTPException(status_code=403, detail="Accès limité à votre direction.")
    return await svc.list_by_direction(direction_id)


@director_router.post("/", response_model=RoutingRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_director_rule(
    body: RoutingRuleCreate,
    actor=Depends(get_current_user),
    svc: RoutingRuleService = Depends(_svc),
):
    """Directeur : crée une règle ciblant obligatoirement SA direction."""
    data = body.dict()
    if actor.role == "director":
        if str(data.get("target_direction_id", "")) != str(actor.direction_id):
            raise HTTPException(
                status_code=403,
                detail="Vous ne pouvez créer des règles que pour votre direction.",
            )
    return await svc.create(data)


@director_router.patch("/{id}", response_model=RoutingRuleResponse)
async def update_director_rule(
    id: str,
    body: RoutingRuleUpdate,
    actor=Depends(get_current_user),
    svc: RoutingRuleService = Depends(_svc),
):
    """Directeur : modifie uniquement les règles de SA direction."""
    if actor.role == "director":
        existing = await svc.get_by_id(id)
        if str(getattr(existing, "target_direction_id", "")) != str(actor.direction_id):
            raise HTTPException(status_code=403, detail="Accès limité à votre direction.")
    return await svc.update(id, body.dict(exclude_unset=True))


@director_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_director_rule(
    id: str,
    actor=Depends(get_current_user),
    svc: RoutingRuleService = Depends(_svc),
):
    """Directeur : supprime uniquement les règles de SA direction."""
    if actor.role == "director":
        existing = await svc.get_by_id(id)
        if str(getattr(existing, "target_direction_id", "")) != str(actor.direction_id):
            raise HTTPException(status_code=403, detail="Accès limité à votre direction.")
    await svc.delete(id)
