from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


# ── Response de base (BaseColumns) ───────────────────────────────────────────

class BaseResponse(BaseModel):
    id: int
    uuid: str
    status: bool
    infos: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedResponse(GenericModel, Generic[T]):
    """Réponse paginée générique : PaginatedResponse[RequestResponse]."""
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    class Config:
        orm_mode = True


class PaginationParams(BaseModel):
    """Paramètres de pagination (query params)."""
    page: int = 1
    page_size: int = 20

    def offset(self) -> int:
        return (self.page - 1) * self.page_size


# ── Recherche / filtres communs ───────────────────────────────────────────────

class BaseSearchParams(BaseModel):
    """Filtres communs à tous les endpoints de liste."""
    q: Optional[str] = None          # recherche texte libre
    status: Optional[bool] = None    # 1=actif, 0=inactif, None=tous
    deleted: bool = False            # True = inclure les soft-deleted
    sort_by: str = "created_at"
    sort_dir: str = "desc"           # asc | desc
