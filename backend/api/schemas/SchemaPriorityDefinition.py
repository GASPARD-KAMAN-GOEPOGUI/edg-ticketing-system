from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel

from .base import BaseResponse

_COLOR = ["slate", "blue", "teal", "amber", "orange", "red", "purple"]


class PriorityDefinitionBase(BaseModel):
    slug: str
    label: str
    description: str = ""
    color: str = "slate"
    sort_order: int
    is_builtin: bool = False


class PriorityDefinitionCreate(PriorityDefinitionBase):
    pass


class PriorityDefinitionUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class PriorityDefinitionResponse(BaseResponse):
    slug: str
    label: str
    description: str
    color: str
    sort_order: int
    is_builtin: bool

    class Config:
        orm_mode = True
