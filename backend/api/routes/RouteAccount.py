from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.phone import normalize_phone
from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaAccount import AccountCreate, AccountUpdate, AccountResponse
from api.schemas.base import PaginatedResponse
from api.services import AccountService

router = APIRouter(
    prefix="/accounts",
    tags=["accounts"],
    dependencies=[Depends(get_current_user)],
)

_admin = Depends(require_roles("admin"))
_assign = Depends(require_roles("agent", "chief", "director", "admin"))


def _svc(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_accounts(
    _actor=_admin,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: AccountService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/agents", response_model=PaginatedResponse)
async def list_agents(
    _actor=_assign,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: AccountService = Depends(_svc),
):
    return await svc.list_agents(page=page, limit=limit)


@router.get("/available-agents", response_model=PaginatedResponse)
async def list_available_agents(
    _actor=_assign,
    direction_id: Optional[int] = Query(None),
    unit_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: AccountService = Depends(_svc),
):
    """Agents disponibles pour l'assignation (filtrable par direction/unité)."""
    items, total = await svc.repo.list_agents(
        direction_id=direction_id,
        unit_id=unit_id,
        availability="available",
        page=page,
        limit=limit,
    )
    return svc.paginate(items, total, page, limit)


@router.get("/by-role/{role}", response_model=PaginatedResponse)
async def list_by_role(
    role: str,
    _actor=_admin,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: AccountService = Depends(_svc),
):
    return await svc.list_by_role(role, page=page, limit=limit)


@router.get("/by-direction/{direction_id}", response_model=PaginatedResponse)
async def list_by_direction(
    direction_id: int,
    _actor=_assign,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    svc: AccountService = Depends(_svc),
):
    return await svc.list_by_direction(direction_id, page=page, limit=limit)


@router.get("/search", response_model=PaginatedResponse)
async def search_accounts(
    _actor=_admin,
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: AccountService = Depends(_svc),
):
    return await svc.search(q, page=page, limit=limit)


@router.get("/check-duplicate")
async def check_duplicate(
    _actor=Depends(get_current_user),
    email: Optional[str] = Query(None),
    matricule: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    exclude_id: Optional[int] = Query(None, description="ID du compte à exclure (pour la modification)"),
    svc: AccountService = Depends(_svc),
):
    """
    Vérifie en temps réel si un e-mail, matricule ou téléphone est déjà utilisé.
    Retourne { email: bool, matricule: bool, phone: bool } — true = déjà pris.
    """
    result: dict = {}
    if email:
        found = await svc.repo.find_by_email(email.strip().lower())
        result["email"] = found is not None and (exclude_id is None or found.id != exclude_id)
    if matricule:
        found = await svc.repo.find_by_matricule(matricule.strip())
        result["matricule"] = found is not None and (exclude_id is None or found.id != exclude_id)
    if phone:
        normalized = normalize_phone(phone.strip())
        found = await svc.repo.find_by_phone(normalized)
        result["phone"] = found is not None and (exclude_id is None or found.id != exclude_id)
    return result


@router.get("/{id}", response_model=AccountResponse)
async def get_account(id: int, _actor=_admin, svc: AccountService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    _actor=_admin,
    svc: AccountService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.patch("/{id}", response_model=AccountResponse)
async def update_account(
    id: int,
    body: AccountUpdate,
    _actor=_admin,
    svc: AccountService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.post("/{id}/verify-email", response_model=AccountResponse)
async def verify_email(id: int, _actor=_admin, svc: AccountService = Depends(_svc)):
    return await svc.verify_email(id)


@router.patch("/{id}/availability", response_model=AccountResponse)
async def set_availability(
    id: int,
    _actor=_assign,
    availability: str = Query(...),
    svc: AccountService = Depends(_svc),
):
    return await svc.set_availability(id, availability)


@router.post("/{id}/activate", status_code=status.HTTP_200_OK)
async def activate_account(id: int, _actor=_admin, svc: AccountService = Depends(_svc)):
    await svc.activate(id)
    return {"ok": True}


@router.post("/{id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_account(id: int, _actor=_admin, svc: AccountService = Depends(_svc)):
    await svc.deactivate(id)
    return {"ok": True}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(id: int, _actor=_admin, svc: AccountService = Depends(_svc)):
    await svc.delete(id)
