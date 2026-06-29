from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class SlaPolicyBase(BaseModel):
    category: str
    priority: str
    response_h: int
    resolution_h: int
    escalate_after_h: int


class SlaPolicyCreate(SlaPolicyBase):
    infos: Optional[Any] = None


class SlaPolicyUpdate(BaseModel):
    response_h: Optional[int] = None
    resolution_h: Optional[int] = None
    escalate_after_h: Optional[int] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class SlaPolicyResponse(BaseResponse):
    category: str
    priority: str
    response_h: int
    resolution_h: int
    escalate_after_h: int

    class Config:
        orm_mode = True
