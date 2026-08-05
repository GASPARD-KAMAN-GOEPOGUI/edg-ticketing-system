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
    status_reason: Optional[str] = None
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


class _RequestCommonFields(BaseResponse):
    """
    Champs communs liste + détail. `timelines`/`appreciation` sont volontairement
    exclus d'ici : ils ne sont utiles que sur la page détail d'un ticket, pas sur
    les dashboards/listes (jusqu'à 500 tickets d'un coup pour chef/direction/DG) —
    voir RequestListItemResponse vs RequestResponse ci-dessous.
    """
    unity_id: Optional[int] = None
    unit_id: Optional[int] = None       # alias de unity_id — compatibilité frontend
    direction_id: Optional[int] = None  # réservé (pas de colonne direction séparée)
    on_behalf_unity_id: Optional[int] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    requester_id: Optional[int] = None
    requester_unit_id: Optional[int] = None
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

    @validator("unit_id", always=True)
    def _fill_unit_id(cls, v, values):
        return v if v is not None else values.get("unity_id")

    class Config:
        orm_mode = True


class RequestListItemResponse(_RequestCommonFields):
    """Schéma allégé pour les listes/dashboards — sans historique de workflow ni CSAT."""
    pass


class SlaCycleResponse(BaseModel):
    """BR-SLA-REOPEN-001 — un cycle SLA (premier traitement ou après réouverture),
    reconstruit depuis `workflow_detail` (voir `ModelRequest.sla_cycles`)."""
    cycle_number: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    sla_hours: Optional[int] = None
    elapsed_hours: Optional[float] = None
    response_hours: Optional[float] = None
    breached: Optional[bool] = None
    resolved_by: Optional[str] = None
    reopen_reason: Optional[str] = None
    closed: bool = False


class InterventionResponse(BaseModel):
    """BR-TRACE-001 — conteneur logique du travail complet d'un intervenant
    (voir `ModelRequest.interventions`) : identification/ordre explicitement
    enregistrés (jamais recalculés), identité figée, temps, travail, décision."""
    intervention_id: str
    cycle_number: int
    intervention_order: Optional[int] = None
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    actor_matricule: Optional[str] = None
    actor_direction_label: Optional[str] = None
    actor_department_label: Optional[str] = None
    actor_service_label: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    work_done: Optional[str] = None
    instruction: Optional[str] = None
    transmission_reason: Optional[str] = None
    decision: Optional[str] = None
    destination_id: Optional[str] = None
    destination_name: Optional[str] = None
    summary: Optional[str] = None
    solution: Optional[str] = None
    recommendations: Optional[str] = None
    sla_hours: Optional[int] = None
    sla_breached: Optional[bool] = None
    comment_count: int = 0
    attachment_count: int = 0
    event_ids: list[str] = []


class RequestResponse(_RequestCommonFields):
    """Schéma complet — page détail d'un ticket (historique + appréciation CSAT)."""
    timelines: list[WorkflowDetailResponse] = []
    appreciation: Optional[AppreciationResponse] = None
    sla_cycles: list[SlaCycleResponse] = []
    reopen_count: int = 0
    interventions: list[InterventionResponse] = []


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
