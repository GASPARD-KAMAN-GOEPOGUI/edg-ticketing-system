from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class AnnouncementCategoryBase(BaseModel):
    code: str
    label: str
    sort_order: int = 0
    is_builtin: bool = False


class AnnouncementCategoryCreate(AnnouncementCategoryBase):
    pass


class AnnouncementCategoryUpdate(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class AnnouncementCategoryResponse(BaseResponse):
    code: str
    label: str
    sort_order: int
    is_builtin: bool

    class Config:
        orm_mode = True
