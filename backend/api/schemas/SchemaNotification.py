from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class NotificationBase(BaseModel):
    recipient_id: int
    request_id: Optional[int] = None
    type: str = "info"
    channel: str = "in_app"
    title: str
    body: str
    action_label: Optional[str] = None
    action_url: Optional[str] = None
    visibility: str = "public"


class NotificationCreate(NotificationBase):
    infos: Optional[Any] = None


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None
    read_at: Optional[datetime] = None


class NotificationResponse(BaseResponse):
    recipient_id: int
    request_id: Optional[int] = None
    type: str
    channel: str
    title: str
    body: str
    action_label: Optional[str] = None
    action_url: Optional[str] = None
    is_read: bool
    visibility: str
    read_at: Optional[datetime] = None

    class Config:
        orm_mode = True
