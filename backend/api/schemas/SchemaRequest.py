from __future__ import annotations

from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, validator

from api.core.enums import RequestSourceEnum
from .base import BaseResponse
from .SchemaWorkflowDetail import WorkflowDetailResponse, WorkflowDetailStepSchema
from .SchemaAppreciation import AppreciationResponse


class RequestBase(BaseModel):
    # Affectation organisationnelle
    unity_id: Optional[int] = None
    unit_id: Optional[int] = None
    direction_id: Optional[int] = None
    assignee_id: Optional[int] = None

    # Demandeur interne
    requester_id: Optional[int] = None

    # Pour compte d'une unité
    on_behalf_unity_id: Optional[int] = None

    title: str
    description: str
    category: str
    is_external: bool
    requester_type: Optional[str] = None
    submission_mode: str = "personal"
    request_status: str = "new"
    priority: str = "medium"
    source: Optional[RequestSourceEnum] = None

    # Demandeur externe
    requester_name: str = ""
    requester_phone: Optional[str] = None
    requester_email: Optional[str] = None
    requester_address: Optional[str] = None
    meter_number: Optional[str] = None
    client_ref: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_label: Optional[str] = None


class RequestCreate(RequestBase):
    infos: Optional[Any] = None
    # Pattern edgrh DemandWorkflowCreateSchema.workflows — création atomique demande + circuit
    workflows: Optional[List[WorkflowDetailStepSchema]] = None


class RequestWorkflowCreate(RequestCreate):
    """Alias explicite pour création avec circuit de validation intégré (pattern edgrh)."""
    pass


class RequestUpdate(BaseModel):
    unity_id: Optional[int] = None
    unit_id: Optional[int] = None
    direction_id: Optional[int] = None
    assignee_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    request_status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    in_triage: Optional[bool] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_label: Optional[str] = None
    sla_hours: Optional[int] = None
    sla_elapsed: Optional[int] = None
    sla_breached: Optional[bool] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None
    sla_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class RequestResponse(BaseResponse):
    unity_id: Optional[int] = None
    unit_id: Optional[int] = None       # alias de unity_id — compatibilité frontend
    direction_id: Optional[int] = None  # réservé (pas de colonne direction séparée)
    on_behalf_unity_id: Optional[int] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    requester_id: Optional[int] = None
    merged_into_id: Optional[int] = None
    ref: str
    title: str
    description: str
    request_status: str
    priority: str
    category: str
    source: Optional[str] = None
    in_triage: bool
    is_external: bool
    requester_type: Optional[str] = None
    submission_mode: str
    requester_name: str
    requester_phone: Optional[str] = None
    requester_email: Optional[str] = None
    requester_address: Optional[str] = None
    meter_number: Optional[str] = None
    client_ref: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    location_label: Optional[str] = None
    sla_hours: int
    sla_elapsed: int
    sla_breached: bool
    sla_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    timelines: list[WorkflowDetailResponse] = []
    appreciation: Optional[AppreciationResponse] = None

    @validator("unit_id", always=True)
    def _fill_unit_id(cls, v, values):
        return v if v is not None else values.get("unity_id")

    class Config:
        orm_mode = True


class RequestSearch(BaseModel):
    """Paramètres de filtrage pour GET /requests/items/ — miroir de edgrh.DemandSearchSchema."""
    id: Optional[int] = None
    uuid: Optional[str] = None
    ref: Optional[str] = None
    requester_id: Optional[int] = None
    assignee_id: Optional[int] = None
    unity_id: Optional[int] = None
    category: Optional[str] = None
    request_status: Optional[str] = None
    priority: Optional[str] = None
    is_external: Optional[bool] = None
    in_triage: Optional[bool] = None
    sla_breached: Optional[bool] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
