from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class AnnouncementTargetRoleBase(BaseModel):
    announcement_id: int
    role: str


class AnnouncementTargetRoleCreate(AnnouncementTargetRoleBase):
    infos: Optional[Any] = None


class AnnouncementTargetRoleUpdate(BaseModel):
    status: Optional[bool] = None
    infos: Optional[Any] = None


class AnnouncementTargetRoleResponse(BaseResponse):
    announcement_id: int
    role: str

    class Config:
        orm_mode = True
