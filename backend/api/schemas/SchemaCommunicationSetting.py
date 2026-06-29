from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class CommunicationSettingBase(BaseModel):
    updated_by: Optional[int] = None
    internal_notif_on: bool = True
    email_on: bool = True
    sms_on: bool = True
    banner_on: bool = True
    whatsapp_on: bool = False
    push_mobile_on: bool = False
    sender_email: str = "noreply@edg.gn"
    sender_sms: str = "EDG"
    reply_to: str = "support@edg.gn"


class CommunicationSettingCreate(CommunicationSettingBase):
    infos: Optional[Any] = None


class CommunicationSettingUpdate(BaseModel):
    updated_by: Optional[int] = None
    internal_notif_on: Optional[bool] = None
    email_on: Optional[bool] = None
    sms_on: Optional[bool] = None
    banner_on: Optional[bool] = None
    whatsapp_on: Optional[bool] = None
    push_mobile_on: Optional[bool] = None
    sender_email: Optional[str] = None
    sender_sms: Optional[str] = None
    reply_to: Optional[str] = None
    infos: Optional[Any] = None


class CommunicationSettingResponse(BaseResponse):
    updated_by: Optional[int] = None
    internal_notif_on: bool
    email_on: bool
    sms_on: bool
    banner_on: bool
    whatsapp_on: bool
    push_mobile_on: bool
    sender_email: str
    sender_sms: str
    reply_to: str

    class Config:
        orm_mode = True
