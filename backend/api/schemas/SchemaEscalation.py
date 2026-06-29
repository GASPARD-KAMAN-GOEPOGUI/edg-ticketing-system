from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from api.models.ModelWorkflowDetail import WorkflowDetail


class EscalationResponse(BaseModel):
    """Réponse escalade — construit depuis WorkflowDetail (event_type='escalation_manual')."""
    id: int
    request_id: str
    request_ref: str
    title: str
    from_user_id: Optional[str] = None
    from_agent_name: str
    to_user_id: Optional[str] = None
    to_agent_name: str
    level: str
    reason: str
    sla_over_hours: int
    priority: str
    escalation_status: str  # open | reviewed | resolved
    dg_comment: Optional[str] = None
    status: bool
    infos: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

    @classmethod
    def from_detail(
        cls,
        wd: "WorkflowDetail",
        request_id: int | str,
        request_ref: str,
    ) -> "EscalationResponse":
        infos: dict = wd.infos or {}
        return cls(
            id=wd.id,
            request_id=str(request_id),
            request_ref=request_ref,
            title=wd.label or "",
            from_user_id=str(infos.get("actor_id")) if infos.get("actor_id") else None,
            from_agent_name=wd.actor_name or "",
            to_user_id=str(infos.get("to_user_id")) if infos.get("to_user_id") else None,
            to_agent_name=infos.get("to_agent_name", ""),
            level=infos.get("level", ""),
            reason=wd.comment or "",
            sla_over_hours=int(infos.get("sla_over_hours", 0)),
            priority=infos.get("priority", ""),
            escalation_status=infos.get("status", "open"),
            dg_comment=infos.get("dg_comment"),
            status=bool(wd.status),
            infos=infos,
            created_at=wd.created_at,
            updated_at=wd.updated_at,
        )


class PaginatedEscalations(BaseModel):
    items: list[EscalationResponse]
    total: int
    page: int
    pages: int
