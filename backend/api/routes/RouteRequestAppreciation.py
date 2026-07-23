from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user
from api.core.rbac import normalize_role
from api.routes.RouteRequest import _check_request_access
from api.schemas.SchemaAppreciation import (
    AppreciationResponse,
    AppreciationSubmit,
    AppreciationUpdateRequest,
)
from api.services import AppreciationService, RequestService

router = APIRouter(
    prefix="/requests",
    tags=["csat"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> AppreciationService:
    return AppreciationService(db)


def _req_svc(db: AsyncSession = Depends(get_db)) -> RequestService:
    return RequestService(db)


def _check_appreciation_owner(actor, req) -> None:
    """3.2 — seul le demandeur ou admin peut soumettre/modifier l'appréciation CSAT."""
    if normalize_role(actor.role) == "admin":
        return
    if str(req.requester_id) != str(actor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : vous ne pouvez soumettre ou modifier que l'appréciation de vos propres demandes.",
        )


@router.get("/{request_id}/appreciation", response_model=Optional[AppreciationResponse])
async def get_request_appreciation(
    request_id: str,
    actor=Depends(get_current_user),
    svc: AppreciationService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    """3.2 — visible par le demandeur, le périmètre agent/chef/directeur de la demande, ou admin."""
    req = await req_svc.get_by_id(request_id)
    _check_request_access(actor, req)
    return await svc.get_by_request_or_none(request_id)


@router.post(
    "/{request_id}/appreciation",
    response_model=AppreciationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_request_appreciation(
    request_id: str,
    body: AppreciationSubmit,
    actor=Depends(get_current_user),
    svc: AppreciationService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    """3.2 — seul le demandeur (ou admin) peut soumettre l'appréciation."""
    req = await req_svc.get_by_id(request_id)
    _check_appreciation_owner(actor, req)
    return await svc.create_for_request(request_id, body.dict())


@router.patch("/{request_id}/appreciation", response_model=AppreciationResponse)
async def update_request_appreciation(
    request_id: str,
    body: AppreciationUpdateRequest,
    actor=Depends(get_current_user),
    svc: AppreciationService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    """3.2 — seul le demandeur (ou admin) peut modifier l'appréciation."""
    req = await req_svc.get_by_id(request_id)
    _check_appreciation_owner(actor, req)
    return await svc.update_for_request(request_id, body.dict(exclude_unset=True))
