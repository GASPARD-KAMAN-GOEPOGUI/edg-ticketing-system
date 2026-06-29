from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class WorkflowDetailBase(BaseModel):
    workflow_id: Optional[int] = None
    unity_id: Optional[int] = None
    agent_id: Optional[int] = None
    task_id: Optional[int] = None
    parent_id: Optional[int] = None
    event_type: Optional[str] = None
    label: Optional[str] = None
    actor_name: Optional[str] = None
    accepted: Optional[bool] = None
    activated: bool = False
    comment: Optional[str] = None


class WorkflowDetailCreate(WorkflowDetailBase):
    infos: Optional[Any] = None


class WorkflowDetailUpdate(BaseModel):
    unity_id: Optional[int] = None
    agent_id: Optional[int] = None
    task_id: Optional[int] = None
    accepted: Optional[bool] = None
    activated: Optional[bool] = None
    comment: Optional[str] = None
    event_type: Optional[str] = None
    label: Optional[str] = None
    actor_name: Optional[str] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class WorkflowDetailStepSchema(BaseModel):
    """Schéma pour décrire une étape dans la création d'un circuit complet.
    Miroir de edgrh.DetailWorkflowCreate02Schema (agent_id au lieu de personel_id)."""
    agent_id: Optional[int] = None
    unity_id: Optional[int] = None
    task_id: Optional[int] = None
    parent_id: Optional[int] = None
    label: Optional[str] = None
    actor_name: Optional[str] = None
    accepted: Optional[bool] = None
    activated: bool = False


class WorkflowDetailAcceptSchema(BaseModel):
    """Schéma pour l'action d'acceptation / refus d'une étape."""
    accepted: bool
    comment: Optional[str] = None


class WorkflowDetailResponse(BaseResponse):
    workflow_id: Optional[int] = None
    unity_id: Optional[int] = None
    agent_id: Optional[int] = None
    task_id: Optional[int] = None
    parent_id: Optional[int] = None
    event_type: Optional[str] = None
    label: Optional[str] = None
    actor_name: Optional[str] = None
    accepted: Optional[bool] = None
    activated: bool
    comment: Optional[str] = None

    class Config:
        orm_mode = True
