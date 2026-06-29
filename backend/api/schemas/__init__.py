"""
Barrel d'imports — tous les schémas Pydantic (v1, orm_mode=True).
Pattern : {Name}Base / {Name}Create / {Name}Update / {Name}Response
"""
from __future__ import annotations

# ── Tables de référence dynamiques (8) ───────────────────────────────────────
# workflow_status, request_source, task_type, task_status → api.core.enums
from .SchemaRequestStatus import (
    RequestStatusBase, RequestStatusCreate, RequestStatusUpdate, RequestStatusResponse,
)
from .SchemaRequestCategory import (
    RequestCategoryBase, RequestCategoryCreate, RequestCategoryUpdate, RequestCategoryResponse,
)
from .SchemaAccountStatus import (
    AccountStatusBase, AccountStatusCreate, AccountStatusUpdate, AccountStatusResponse,
)
from .SchemaKnowledgeCategory import (
    KnowledgeCategoryBase, KnowledgeCategoryCreate, KnowledgeCategoryUpdate, KnowledgeCategoryResponse,
)
from .SchemaAnnouncementCategory import (
    AnnouncementCategoryBase, AnnouncementCategoryCreate,
    AnnouncementCategoryUpdate, AnnouncementCategoryResponse,
)
from .SchemaAnnouncementPriority import (
    AnnouncementPriorityBase, AnnouncementPriorityCreate,
    AnnouncementPriorityUpdate, AnnouncementPriorityResponse,
)
from .SchemaAnnouncementStatus import (
    AnnouncementStatusBase, AnnouncementStatusCreate,
    AnnouncementStatusUpdate, AnnouncementStatusResponse,
)
from .SchemaPriorityDefinition import (
    PriorityDefinitionBase, PriorityDefinitionCreate,
    PriorityDefinitionUpdate, PriorityDefinitionResponse,
)

# ── Structure organisationnelle ───────────────────────────────────────────────
from .SchemaUnity import (
    UnityBase, UnityCreate, UnityUpdate, UnityResponse,
)
from .SchemaOrganigram import (
    OrganigramBase, OrganigramCreate, OrganigramUpdate, OrganigramResponse,
)
from .SchemaAccount import (
    AccountBase, AccountCreate, AccountUpdate, AccountResponse,
)

# ── Request & enfants ─────────────────────────────────────────────────────────
from .SchemaRequest import (
    RequestBase, RequestCreate, RequestUpdate, RequestResponse,
)
from .SchemaAttachment import (
    AttachmentBase, AttachmentCreate, AttachmentUpdate, AttachmentResponse,
)
# ── Configuration ─────────────────────────────────────────────────────────────
from .SchemaSlaPolicy import (
    SlaPolicyBase, SlaPolicyCreate, SlaPolicyUpdate, SlaPolicyResponse,
)
from .SchemaRoutingRule import (
    RoutingRuleBase, RoutingRuleCreate, RoutingRuleUpdate, RoutingRuleResponse,
)

# ── Workflow ──────────────────────────────────────────────────────────────────
from .SchemaWorkflow import (
    WorkflowBase, WorkflowCreate, WorkflowUpdate, WorkflowResponse,
)
from .SchemaWorkflowDetail import (
    WorkflowDetailBase, WorkflowDetailCreate,
    WorkflowDetailUpdate, WorkflowDetailResponse,
)
from .SchemaTask import (
    TaskBase, TaskCreate, TaskUpdate, TaskResponse,
)

# ── Transverses ───────────────────────────────────────────────────────────────
from .SchemaNotification import (
    NotificationBase, NotificationCreate, NotificationUpdate, NotificationResponse,
)
from .SchemaKnowledgeArticle import (
    KnowledgeArticleBase, KnowledgeArticleCreate,
    KnowledgeArticleUpdate, KnowledgeArticleResponse,
)
from .SchemaActivityLog import (
    ActivityLogCreate, ActivityLogResponse,
)

# ── Communication & CSAT ──────────────────────────────────────────────────────
from .SchemaAnnouncement import (
    AnnouncementBase, AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
)
from .SchemaAnnouncementTargetRole import (
    AnnouncementTargetRoleBase, AnnouncementTargetRoleCreate,
    AnnouncementTargetRoleUpdate, AnnouncementTargetRoleResponse,
)
from .SchemaCommunicationSetting import (
    CommunicationSettingBase, CommunicationSettingCreate,
    CommunicationSettingUpdate, CommunicationSettingResponse,
)
from .SchemaAppreciation import (
    AppreciationBase, AppreciationCreate, AppreciationUpdate, AppreciationResponse,
)
