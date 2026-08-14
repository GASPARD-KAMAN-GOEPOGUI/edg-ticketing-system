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
from .ModelAccountStatus import AccountStatus
from .ModelKnowledgeCategory import KnowledgeCategory
from .ModelAnnouncementCategory import AnnouncementCategory
from .ModelAnnouncementStatus import AnnouncementStatus
from .ModelAnnouncementPriority import AnnouncementPriority
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
from .ModelKnowledgeArticle import KnowledgeArticle
from .ModelActivityLog import ActivityLog

# ── Communication & CSAT (4) ─────────────────────────────────────────────────
from .ModelAnnouncement import Announcement
from .ModelAnnouncementTargetRole import AnnouncementTargetRole
from .ModelCommunicationSetting import CommunicationSetting
from .ModelAppreciation import Appreciation

__all__ = [
    # Référence (8)
    "RequestStatus", "RequestCategory", "AccountStatus",
    "KnowledgeCategory",
    "AnnouncementCategory", "AnnouncementStatus", "AnnouncementPriority",
    "PriorityDefinition",
    # Organisation (2)
    "Unity", "Organigram",
    # Métier (1)
    "Account",
    # Request (2)
    "Request", "Attachment",
    # Workflow (3)
    "Workflow", "Task", "WorkflowDetail",
    # Configuration (2)
    "SlaPolicy", "RoutingRule",
    # Transverses (3)
    "Notification", "KnowledgeArticle", "ActivityLog",
    # Communication & CSAT (4)
    "Announcement", "AnnouncementTargetRole",
    "CommunicationSetting", "Appreciation",
]
