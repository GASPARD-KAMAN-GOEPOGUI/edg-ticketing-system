"""
Barrel export — tous les repositories EDG Connect.
Pattern : Repository{NomModèle}
"""
from api.repositories.base_repository import (
    BaseRepository,
    ReferenceBaseRepository,
    NotFoundException,
    RepositoryIntegrityError,
)

# ── Tables de référence (8) ───────────────────────────────────────────────────
from api.repositories.RepositoryRequestStatus import RequestStatusRepository
from api.repositories.RepositoryRequestCategory import RequestCategoryRepository
from api.repositories.RepositoryAccountStatus import AccountStatusRepository
from api.repositories.RepositoryKnowledgeCategory import KnowledgeCategoryRepository
from api.repositories.RepositoryAnnouncementCategory import AnnouncementCategoryRepository
from api.repositories.RepositoryAnnouncementPriority import AnnouncementPriorityRepository
from api.repositories.RepositoryAnnouncementStatus import AnnouncementStatusRepository
from api.repositories.RepositoryPriorityDefinition import PriorityDefinitionRepository

# ── Structure organisationnelle ───────────────────────────────────────────────
from api.repositories.RepositoryUnity import UnityRepository
from api.repositories.RepositoryOrganigram import OrganigramRepository
from api.repositories.RepositoryAccount import AccountRepository

# ── Requêtes et chaîne ────────────────────────────────────────────────────────
from api.repositories.RepositoryRequest import RequestRepository
from api.repositories.RepositoryAttachment import AttachmentRepository

# ── Configuration métier ──────────────────────────────────────────────────────
from api.repositories.RepositorySlaPolicy import SlaPolicyRepository
from api.repositories.RepositoryRoutingRule import RoutingRuleRepository

# ── Workflow & tâches ─────────────────────────────────────────────────────────
from api.repositories.RepositoryWorkflow import WorkflowRepository
from api.repositories.RepositoryWorkflowDetail import WorkflowDetailRepository
from api.repositories.RepositoryTask import TaskRepository

# ── Transversal ───────────────────────────────────────────────────────────────
from api.repositories.RepositoryNotification import NotificationRepository
from api.repositories.RepositoryActivityLog import ActivityLogRepository
from api.repositories.RepositoryKnowledgeArticle import KnowledgeArticleRepository
from api.repositories.RepositoryCommunicationSetting import CommunicationSettingRepository

# ── Sécurité incidents ────────────────────────────────────────────────────────
from api.repositories.RepositorySecurityIncident import SecurityIncidentRepository

# ── Communication & CSAT ──────────────────────────────────────────────────────
from api.repositories.RepositoryAnnouncement import AnnouncementRepository
from api.repositories.RepositoryAnnouncementTargetRole import AnnouncementTargetRoleRepository
from api.repositories.RepositoryAppreciation import AppreciationRepository

__all__ = [
    "BaseRepository", "ReferenceBaseRepository",
    "NotFoundException", "RepositoryIntegrityError",
    "RequestStatusRepository", "RequestCategoryRepository",
    "AccountStatusRepository", "KnowledgeCategoryRepository",
    "AnnouncementCategoryRepository", "AnnouncementPriorityRepository",
    "AnnouncementStatusRepository", "PriorityDefinitionRepository",
    "UnityRepository", "OrganigramRepository", "AccountRepository",
    "RequestRepository", "AttachmentRepository",
    "SlaPolicyRepository", "RoutingRuleRepository",
    "WorkflowRepository", "WorkflowDetailRepository", "TaskRepository",
    "NotificationRepository", "ActivityLogRepository",
    "KnowledgeArticleRepository", "CommunicationSettingRepository",
    "SecurityIncidentRepository",
    "AnnouncementRepository", "AnnouncementTargetRoleRepository",
    "AppreciationRepository",
]
