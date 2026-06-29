from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse
from .SchemaUnity import UnityResponse


class OrganigramBase(BaseModel):
    unity_id: int
    parent_id: Optional[int] = None


class OrganigramCreate(OrganigramBase):
    infos: Optional[Any] = None


class OrganigramUpdate(BaseModel):
    unity_id: Optional[int] = None
    parent_id: Optional[int] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class OrganigramResponse(BaseResponse):
    unity_id: int
    parent_id: Optional[int] = None
    unity: Optional[UnityResponse] = None

    class Config:
        orm_mode = True
