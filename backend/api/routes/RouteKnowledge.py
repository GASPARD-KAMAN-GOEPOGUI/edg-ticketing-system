from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException
from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaKnowledgeArticle import (
    KnowledgeArticleCreate,
    KnowledgeArticleResponse,
    KnowledgeArticleUpdate,
)
from api.schemas.base import PaginatedResponse
from api.services import KnowledgeArticleService

router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(get_current_user)],
)

# Router public : lecture seule des articles publiés, sans authentification (CDC §6.6)
public_router = APIRouter(prefix="/knowledge", tags=["knowledge-public"])

_EDITOR_ROLES = frozenset({"admin", "chief"})


def _svc(db: AsyncSession = Depends(get_db)) -> KnowledgeArticleService:
    return KnowledgeArticleService(db)


# ── Routes spec §4.10 ────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedResponse)
async def list_knowledge(
    published: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    actor=Depends(get_current_user),
    svc: KnowledgeArticleService = Depends(_svc),
):
    is_editor = actor.role in _EDITOR_ROLES
    if q:
        published_only = True if not is_editor else (published is not False)
        return await svc.search(q, published_only=published_only, page=page, limit=limit)
    if published is True or not is_editor:
        return await svc.list_published(category=category, page=page, limit=limit)
    return await svc.list_all(page=page, limit=limit)


@router.get("/{id}", response_model=KnowledgeArticleResponse)
async def get_knowledge(
    id: str,
    actor=Depends(get_current_user),
    svc: KnowledgeArticleService = Depends(_svc),
):
    article = await svc.get_by_id(id)
    if not article.is_published and actor.role not in _EDITOR_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet article n'est pas encore publié.",
        )
    return article


_editor = Depends(require_roles("admin", "chief"))


@router.post("/", response_model=KnowledgeArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    body: KnowledgeArticleCreate,
    _=_editor,
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.put("/{id}", response_model=KnowledgeArticleResponse)
async def update_knowledge(
    id: str,
    body: KnowledgeArticleUpdate,
    _=_editor,
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


class PublishBody(BaseModel):
    published: bool = True


@router.put("/{id}/publish", response_model=KnowledgeArticleResponse)
async def toggle_publish(
    id: str,
    body: PublishBody = PublishBody(),
    _=_editor,
    svc: KnowledgeArticleService = Depends(_svc),
):
    if body.published:
        return await svc.publish(id)
    return await svc.update(id, {"is_published": False})


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(
    id: str,
    _=Depends(require_roles("admin")),
    svc: KnowledgeArticleService = Depends(_svc),
):
    await svc.delete(id)


# ── Routes publiques (sans authentification, CDC §6.6) ───────────────────────

@public_router.get("/public", response_model=PaginatedResponse)
async def list_knowledge_public(
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: KnowledgeArticleService = Depends(_svc),
):
    """Articles publiés accessibles sans authentification (landing + /knowledge public)."""
    if q:
        return await svc.search(q, published_only=True, page=page, limit=limit)
    return await svc.list_published(category=category, page=page, limit=limit)


@public_router.get("/public/{id}", response_model=KnowledgeArticleResponse)
async def get_knowledge_public(
    id: str,
    svc: KnowledgeArticleService = Depends(_svc),
):
    """Détail d'un article publié (sans authentification)."""
    article = await svc.get_by_id(id)
    if not article.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article introuvable.",
        )
    return article
