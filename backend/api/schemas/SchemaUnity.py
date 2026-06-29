from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class UnityBase(BaseModel):
    label: str
    codename: str
    aleas: Optional[str] = None
    description: Optional[str] = None


class UnityCreate(UnityBase):
    infos: Optional[Any] = None


class UnityUpdate(BaseModel):
    label: Optional[str] = None
    codename: Optional[str] = None
    aleas: Optional[str] = None
    description: Optional[str] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class UnityResponse(BaseResponse):
    label: str
    codename: str
    aleas: Optional[str] = None
    description: Optional[str] = None

    class Config:
        orm_mode = True
