from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class AttachmentBase(BaseModel):
    request_id: int
    uploader_id: Optional[int] = None
    filename: str
    storage_path: str
    mime_type: str
    size_bytes: int


class AttachmentCreate(AttachmentBase):
    scan_status: str = "pending_scan"
    infos: Optional[Any] = None


class AttachmentUpdate(BaseModel):
    clamav_clean: Optional[bool] = None
    scan_status: Optional[str] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class AttachmentResponse(BaseResponse):
    request_id: int
    uploader_id: Optional[int] = None
    filename: str
    storage_path: str
    mime_type: str
    size_bytes: int
    clamav_clean: Optional[bool] = None
    scan_status: str

    class Config:
        orm_mode = True
