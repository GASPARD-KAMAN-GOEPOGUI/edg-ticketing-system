from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, validator

from .base import BaseResponse


class AppreciationBase(BaseModel):
    request_id: int
    rating: int
    comment: Optional[str] = None
    resolved_confirmed: bool
    author_type: str

    @validator("rating")
    def rating_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("rating doit être entre 1 et 5")
        return v


class AppreciationCreate(AppreciationBase):
    infos: Optional[Any] = None


class AppreciationUpdate(BaseModel):
    rating: Optional[int] = None
    comment: Optional[str] = None
    resolved_confirmed: Optional[bool] = None
    is_modified: Optional[bool] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None

    @validator("rating")
    def rating_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("rating doit être entre 1 et 5")
        return v


class AppreciationSubmit(BaseModel):
    """Schéma pour POST /requests/:id/appreciation (request_id vient de l'URL)."""
    rating: int
    comment: Optional[str] = None
    resolved_confirmed: bool
    author_type: str = "internal"

    @validator("rating")
    def rating_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("rating doit être entre 1 et 5")
        return v


class AppreciationUpdateRequest(BaseModel):
    """Schéma pour PATCH /requests/:id/appreciation."""
    rating: Optional[int] = None
    comment: Optional[str] = None
    resolved_confirmed: Optional[bool] = None

    @validator("rating")
    def rating_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("rating doit être entre 1 et 5")
        return v


class AppreciationResponse(BaseResponse):
    request_id: int
    rating: int
    comment: Optional[str] = None
    resolved_confirmed: bool
    is_modified: bool
    author_type: str

    class Config:
        orm_mode = True
