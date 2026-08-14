from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from api.core.rbac import normalize_role
from api.schemas.SchemaAppreciation import (
    AppreciationCreate, AppreciationUpdate, AppreciationResponse,
)
from api.schemas.base import PaginatedResponse
from api.services import AppreciationService, RequestService

router = APIRouter(
    prefix="/appreciations",
    tags=["appreciations"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> AppreciationService:
    return AppreciationService(db)


def _req_svc(db: AsyncSession = Depends(get_db)) -> RequestService:
    return RequestService(db)


async def _check_appreciation_ownership(actor, appreciation, req_svc: RequestService) -> None:
    """Seul le requérant ou admin peut modifier/supprimer une appréciation."""
    if normalize_role(actor.role) == "admin":
        return
    req = await req_svc.get_by_id(str(appreciation.request_id))
    if str(req.requester_id) != str(actor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : vous ne pouvez modifier que vos propres appréciations.",
        )


@router.get("/", response_model=PaginatedResponse)
async def list_appreciations(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: AppreciationService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/stats/average")
async def average_rating(
    only_confirmed: bool = Query(True),
    svc: AppreciationService = Depends(_svc),
):
    avg = await svc.average_rating(only_confirmed=only_confirmed)
    return {"average_rating": avg}


@router.get("/stats/distribution")
async def rating_distribution(svc: AppreciationService = Depends(_svc)):
    return await svc.count_by_rating()


@router.get("/by-rating/{rating}", response_model=PaginatedResponse)
async def list_by_rating(
    rating: int,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: AppreciationService = Depends(_svc),
):
    return await svc.list_by_rating(rating, page=page, limit=limit)


@router.get("/by-request/{request_id}", response_model=AppreciationResponse)
async def get_by_request(request_id: str, svc: AppreciationService = Depends(_svc)):
    return await svc.get_by_request(request_id)


@router.get("/{id}", response_model=AppreciationResponse)
async def get_appreciation(id: str, svc: AppreciationService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=AppreciationResponse, status_code=status.HTTP_201_CREATED)
async def create_appreciation(body: AppreciationCreate, svc: AppreciationService = Depends(_svc)):
    return await svc.create(body.dict())


@router.put("/{id}", response_model=AppreciationResponse)
async def update_appreciation(
    id: str,
    body: AppreciationUpdate,
    actor=Depends(get_current_user),
    svc: AppreciationService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    appreciation = await svc.get_by_id(id)
    await _check_appreciation_ownership(actor, appreciation, req_svc)
    return await svc.update(id, body.dict(exclude_unset=True))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appreciation(
    id: str,
    actor=Depends(get_current_user),
    svc: AppreciationService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    appreciation = await svc.get_by_id(id)
    await _check_appreciation_ownership(actor, appreciation, req_svc)
    await svc.delete(id)
