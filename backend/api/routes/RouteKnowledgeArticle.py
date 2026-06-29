from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaKnowledgeArticle import (
    KnowledgeArticleCreate, KnowledgeArticleUpdate, KnowledgeArticleResponse,
)
from api.schemas.base import PaginatedResponse
from api.services import KnowledgeArticleService

router = APIRouter(
    prefix="/knowledge-articles",
    tags=["knowledge-articles"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> KnowledgeArticleService:
    return KnowledgeArticleService(db)


@router.get("/", response_model=PaginatedResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.list_all(page=page, limit=limit)


@router.get("/published", response_model=PaginatedResponse)
async def list_published(
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.list_published(category=category, page=page, limit=limit)


@router.get("/search", response_model=PaginatedResponse)
async def search_articles(
    q: str = Query(..., min_length=1),
    published_only: bool = Query(True),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.search(q, published_only=published_only, page=page, limit=limit)


@router.get("/{id}", response_model=KnowledgeArticleResponse)
async def get_article(id: str, svc: KnowledgeArticleService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.post("/", response_model=KnowledgeArticleResponse, status_code=status.HTTP_201_CREATED)
async def create_article(
    body: KnowledgeArticleCreate,
    _=Depends(require_roles("admin", "chief")),
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.create(body.dict())


@router.patch("/{id}", response_model=KnowledgeArticleResponse)
async def update_article(
    id: str,
    body: KnowledgeArticleUpdate,
    _=Depends(require_roles("admin", "chief")),
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True))


@router.post("/{id}/publish", response_model=KnowledgeArticleResponse)
async def publish_article(
    id: str,
    _=Depends(require_roles("admin", "chief")),
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.publish(id)


@router.post("/{id}/archive", response_model=KnowledgeArticleResponse)
async def archive_article(
    id: str,
    _=Depends(require_roles("admin", "chief")),
    svc: KnowledgeArticleService = Depends(_svc),
):
    return await svc.archive(id)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    id: str,
    _=Depends(require_roles("admin")),
    svc: KnowledgeArticleService = Depends(_svc),
):
    await svc.delete(id)
