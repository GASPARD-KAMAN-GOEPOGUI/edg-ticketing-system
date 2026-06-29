from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class ActivityLogCreate(BaseModel):
    """Append-only — pas de Update ni Delete."""
    actor_id: Optional[int] = None
    actor: str
    actor_role: str
    action: str
    category: str
    target: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    log_status: str
    infos: Optional[Any] = None


class ActivityLogResponse(BaseResponse):
    actor_id: Optional[int] = None
    actor: str
    actor_role: str
    action: str
    category: str
    target: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    log_status: str

    class Config:
        orm_mode = True
