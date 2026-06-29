from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SecurityIncidentCreate(BaseModel):
    identifier: str
    captured_image: str           # base64 data URL
    timestamp: str                # ISO string from frontend
    user_agent: str
    ip_address: Optional[str] = None
    browser: Optional[str] = None
    os_info: Optional[str] = None
    device_type: Optional[str] = None
    location_approx: Optional[str] = None
    attempt_count: int = 1


class SecurityIncidentResponse(BaseModel):
    id: int
    uuid: str
    resolved_by: Optional[int]
    email_attempted: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    browser: Optional[str]
    os_info: Optional[str]
    device_type: Optional[str]
    location_approx: Optional[str]
    photo_path: Optional[str]
    occurred_at: Optional[str]
    attempt_count: int
    resolved: bool
    notes: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class SecurityIncidentResolve(BaseModel):
    notes: Optional[str] = None
