"""
Barrel d'imports — importe tous les modèles ORM pour que SQLAlchemy
enregistre les tables dans Base.metadata et que les relationships
soient résolues sans import circulaire.

26 tables · 8 tables de référence dynamiques · 9 tables métier · 2 tables de configuration — v4.0
workflow_status, request_source, task_type, task_status → enums Python (api.core.enums)
"""
from __future__ import annotations

# ── Tables de référence dynamiques (8) ───────────────────────────────────────
from .ModelRequestStatus import RequestStatus
from .ModelRequestCategory import RequestCategory
from .ModelPriorityDefinition import PriorityDefinition

# ── Structure organisationnelle (2) ──────────────────────────────────────────
from .ModelUnity import Unity
from .ModelOrganigram import Organigram

# ── Tables métier principales (1) ────────────────────────────────────────────
from .ModelAccount import Account

# ── Request et ses dépendances (2) ───────────────────────────────────────────
from .ModelRequest import Request
from .ModelAttachment import Attachment

# ── Workflow (3) ─────────────────────────────────────────────────────────────
from .ModelWorkflow import Workflow
from .ModelTask import Task
from .ModelWorkflowDetail import WorkflowDetail

# ── Configuration (2) ────────────────────────────────────────────────────────
from .ModelSlaPolicy import SlaPolicy
from .ModelRoutingRule import RoutingRule

# ── Tables transverses (3) ───────────────────────────────────────────────────
from .ModelNotification import Notification
from .ModelActivityLog import ActivityLog

# ── Communication & CSAT (4) ─────────────────────────────────────────────────
from .ModelAppreciation import Appreciation

__all__ = [
    "RequestStatus", "RequestCategory", "PriorityDefinition",
    "Unity", "Organigram", "Account",
    "Request", "Attachment", "Workflow",
    "Task", "WorkflowDetail", "SlaPolicy",
    "RoutingRule", "Notification", "ActivityLog",
    "Appreciation",
]
