from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaOrganigram import OrganigramCreate, OrganigramUpdate, OrganigramResponse
from api.schemas.base import PaginatedResponse
from api.services.ServiceOrganigram import OrganigramService

router = APIRouter(
    prefix="/organigrams",
    tags=["organigrams"],
    dependencies=[Depends(get_current_user)],
)

_staff = Depends(require_roles("agent", "chief", "director", "admin"))


def _svc(db: AsyncSession = Depends(get_db)) -> OrganigramService:
    return OrganigramService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_organigrams(
    page: int = Query(1, ge=1),
    limit: int = Query(500, ge=1, le=1000),
    svc: OrganigramService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/roots", response_model=list[OrganigramResponse])
async def list_root_nodes(svc: OrganigramService = Depends(_svc)):
    """Nœuds racines de l'organigramme (Directions, niveau 1)."""
    return await svc.list_roots()


@router.get("/{id}/children", summary="Enfants directs (niveau N+1)")
async def get_children(id: str, _=_staff, svc: OrganigramService = Depends(_svc)):
    return await svc.get_children(id)


@router.get("/{id}/ancestors", summary="Ancêtres jusqu'à la racine")
async def get_ancestors(id: str, _=_staff, svc: OrganigramService = Depends(_svc)):
    return await svc.get_ancestors(id)


@router.get("/{id}/descendants", summary="Tous les descendants (sous-arbre)")
async def get_descendants(id: str, _=_staff, svc: OrganigramService = Depends(_svc)):
    return await svc.get_descendants(id)


@router.get("/{id}/tree", summary="Arbre JSON complet depuis ce nœud")
async def get_tree(id: str, _=_staff, svc: OrganigramService = Depends(_svc)):
    return await svc.get_tree(id)


@router.get("/{id}", response_model=OrganigramResponse)
async def get_organigram(id: str, svc: OrganigramService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=OrganigramResponse, status_code=status.HTTP_201_CREATED)
async def create_organigram(
    body: OrganigramCreate,
    _=Depends(require_roles("admin")),
    svc: OrganigramService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.patch("/{id}", response_model=OrganigramResponse)
async def update_organigram(
    id: str,
    body: OrganigramUpdate,
    _=Depends(require_roles("admin")),
    svc: OrganigramService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organigram(
    id: str,
    _=Depends(require_roles("admin")),
    svc: OrganigramService = Depends(_svc),
):
    await svc.delete(id)
