from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel

from .base import BaseResponse


class _TargetRoleItem(BaseModel):
    role: str

    class Config:
        orm_mode = True


class _TargetDirectionItem(BaseModel):
    direction_id: int

    class Config:
        orm_mode = True


class AnnouncementBase(BaseModel):
    author_id: int
    title: str
    description: str
    announcement_category: str
    announcement_priority: str = "normal"
    announcement_status: str = "draft"
    audience: str = "internal"
    attachment_name: Optional[str] = None
    visibility: str = "public"
    expires_at: Optional[datetime] = None


class AnnouncementCreate(AnnouncementBase):
    infos: Optional[Any] = None
    role_names: List[str] = []
    direction_ids: List[int] = []


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    announcement_category: Optional[str] = None
    announcement_priority: Optional[str] = None
    announcement_status: Optional[str] = None
    audience: Optional[str] = None
    attachment_name: Optional[str] = None
    visibility: Optional[str] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None
    role_names: Optional[List[str]] = None
    direction_ids: Optional[List[int]] = None
    closed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class AnnouncementResponse(BaseResponse):
    author_id: int
    title: str
    description: str
    announcement_category: str
    announcement_priority: str
    announcement_status: str
    audience: str
    attachment_name: Optional[str] = None
    visibility: str
    target_roles: List[_TargetRoleItem] = []
    target_directions: List[_TargetDirectionItem] = []
    published_at: datetime
    closed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        orm_mode = True
