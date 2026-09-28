"""
Barrel export — tous les services EDG Support.
"""
from api.services.base_service import BaseService

# ── Tables de référence (3) ───────────────────────────────────────────────────
from api.services.ServiceReferences import (
    RequestStatusService,
    RequestCategoryService,
    PriorityDefinitionService,
)

# ── Structure organisationnelle ───────────────────────────────────────────────
from api.services.ServiceUnity import UnityService
from api.services.ServiceOrganigram import OrganigramService
from api.services.ServiceAccount import AccountService

# ── Requêtes et chaîne ────────────────────────────────────────────────────────
from api.services.ServiceRequest import RequestService
from api.services.ServiceAttachment import AttachmentService
from api.services.ServiceRequestExport import RequestExportService
from api.services.ServicePvIntervention import PvInterventionService

# ── Configuration métier ──────────────────────────────────────────────────────
from api.services.ServiceSlaPolicy import SlaPolicyService
from api.services.ServiceRoutingRule import RoutingRuleService

# ── Workflow & tâches ─────────────────────────────────────────────────────────
from api.services.ServiceWorkflow import WorkflowService
from api.services.ServiceTask import TaskService

# ── Transversal ───────────────────────────────────────────────────────────────
from api.services.ServiceNotification import NotificationService
from api.services.ServiceActivityLog import ActivityLogService

# ── Communication & CSAT ──────────────────────────────────────────────────────
from api.services.ServiceAppreciation import AppreciationService

# ── Stats ─────────────────────────────────────────────────────────────────────
from api.services.ServiceStats import StatsService

__all__ = [
    "BaseService", "RequestStatusService", "RequestCategoryService",
    "PriorityDefinitionService", "UnityService", "OrganigramService",
    "AccountService", "RequestService", "AttachmentService",
    "RequestExportService", "PvInterventionService", "SlaPolicyService",
    "RoutingRuleService", "WorkflowService", "TaskService",
    "NotificationService", "ActivityLogService", "AppreciationService", "StatsService",
]
