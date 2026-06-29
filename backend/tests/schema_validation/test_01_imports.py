"""
Test 01 — Validation des imports.
Vérifie que chaque fichier de schéma s'importe sans erreur et expose
les classes attendues ({Name}Base / Create / Update / Response).
ActivityLog n'a pas de Base ni Update (append-only).
"""
from __future__ import annotations

import importlib
import pytest


# ── Modules et classes attendues ─────────────────────────────────────────────

SCHEMA_MODULES = [
    # (module_name, [classes_to_check])
    ("backend.api.schemas.SchemaRequestStatus",
     ["RequestStatusBase", "RequestStatusCreate", "RequestStatusUpdate", "RequestStatusResponse"]),
    ("backend.api.schemas.SchemaAccountStatus",
     ["AccountStatusBase", "AccountStatusCreate", "AccountStatusUpdate", "AccountStatusResponse"]),
    ("backend.api.schemas.SchemaAnnouncementCategory",
     ["AnnouncementCategoryBase", "AnnouncementCategoryCreate",
      "AnnouncementCategoryUpdate", "AnnouncementCategoryResponse"]),
    ("backend.api.schemas.SchemaAnnouncementPriority",
     ["AnnouncementPriorityBase", "AnnouncementPriorityCreate",
      "AnnouncementPriorityUpdate", "AnnouncementPriorityResponse"]),
    ("backend.api.schemas.SchemaAnnouncementStatus",
     ["AnnouncementStatusBase", "AnnouncementStatusCreate",
      "AnnouncementStatusUpdate", "AnnouncementStatusResponse"]),
    ("backend.api.schemas.SchemaPriorityDefinition",
     ["PriorityDefinitionBase", "PriorityDefinitionCreate",
      "PriorityDefinitionUpdate", "PriorityDefinitionResponse"]),
    ("backend.api.schemas.SchemaUnity",
     ["UnityBase", "UnityCreate", "UnityUpdate", "UnityResponse"]),
    ("backend.api.schemas.SchemaOrganigram",
     ["OrganigramBase", "OrganigramCreate", "OrganigramUpdate", "OrganigramResponse"]),
    ("backend.api.schemas.SchemaAccount",
     ["AccountBase", "AccountCreate", "AccountUpdate", "AccountResponse"]),
    ("backend.api.schemas.SchemaEmployeeDirectory",
     ["EmployeeDirectoryBase", "EmployeeDirectoryCreate",
      "EmployeeDirectoryUpdate", "EmployeeDirectoryResponse"]),
    ("backend.api.schemas.SchemaRequest",
     ["RequestBase", "RequestCreate", "RequestUpdate", "RequestResponse"]),
    ("backend.api.schemas.SchemaWorkflowDetail",
     ["WorkflowDetailBase", "WorkflowDetailCreate",
      "WorkflowDetailUpdate", "WorkflowDetailResponse"]),
    ("backend.api.schemas.SchemaAttachment",
     ["AttachmentBase", "AttachmentCreate", "AttachmentUpdate", "AttachmentResponse"]),
    ("backend.api.schemas.SchemaCategory",
     ["CategoryBase", "CategoryCreate", "CategoryUpdate", "CategoryResponse"]),
    ("backend.api.schemas.SchemaSlaPolicy",
     ["SlaPolicyBase", "SlaPolicyCreate", "SlaPolicyUpdate", "SlaPolicyResponse"]),
    ("backend.api.schemas.SchemaRoutingRule",
     ["RoutingRuleBase", "RoutingRuleCreate", "RoutingRuleUpdate", "RoutingRuleResponse"]),
    ("backend.api.schemas.SchemaWorkflow",
     ["WorkflowBase", "WorkflowCreate", "WorkflowUpdate", "WorkflowResponse"]),
    ("backend.api.schemas.SchemaWorkflowDetail",
     ["WorkflowDetailBase", "WorkflowDetailCreate",
      "WorkflowDetailUpdate", "WorkflowDetailResponse"]),
    ("backend.api.schemas.SchemaTask",
     ["TaskBase", "TaskCreate", "TaskUpdate", "TaskResponse"]),
    ("backend.api.schemas.SchemaNotification",
     ["NotificationBase", "NotificationCreate", "NotificationUpdate", "NotificationResponse"]),
    ("backend.api.schemas.SchemaKnowledgeArticle",
     ["KnowledgeArticleBase", "KnowledgeArticleCreate",
      "KnowledgeArticleUpdate", "KnowledgeArticleResponse"]),
    # Append-only — pas de Base ni Update
    ("backend.api.schemas.SchemaActivityLog",
     ["ActivityLogCreate", "ActivityLogResponse"]),
    ("backend.api.schemas.SchemaAnnouncement",
     ["AnnouncementBase", "AnnouncementCreate", "AnnouncementUpdate", "AnnouncementResponse"]),
    ("backend.api.schemas.SchemaAnnouncementTargetRole",
     ["AnnouncementTargetRoleBase", "AnnouncementTargetRoleCreate",
      "AnnouncementTargetRoleUpdate", "AnnouncementTargetRoleResponse"]),
    ("backend.api.schemas.SchemaCommunicationSetting",
     ["CommunicationSettingBase", "CommunicationSettingCreate",
      "CommunicationSettingUpdate", "CommunicationSettingResponse"]),
    ("backend.api.schemas.SchemaAppreciation",
     ["AppreciationBase", "AppreciationCreate", "AppreciationUpdate", "AppreciationResponse"]),
]

BARREL_IMPORT = "backend.api.schemas"


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSchemaImports:
    def test_barrel_import_succeeds(self):
        """Le __init__.py du package schemas s'importe sans erreur."""
        mod = importlib.import_module(BARREL_IMPORT)
        assert mod is not None

    @pytest.mark.parametrize("module_name,classes", SCHEMA_MODULES)
    def test_module_import(self, module_name: str, classes: list[str]):
        """Chaque fichier Schema*.py s'importe sans erreur."""
        mod = importlib.import_module(module_name)
        assert mod is not None

    @pytest.mark.parametrize("module_name,classes", SCHEMA_MODULES)
    def test_expected_classes_exposed(self, module_name: str, classes: list[str]):
        """Chaque module expose exactement les classes attendues."""
        mod = importlib.import_module(module_name)
        for cls_name in classes:
            assert hasattr(mod, cls_name), (
                f"{module_name} doit exposer '{cls_name}'"
            )

    def test_base_schemas_import(self):
        """base.py expose BaseResponse, PaginatedResponse, PaginationParams, BaseSearchParams."""
        from backend.api.schemas.base import (
            BaseResponse,
            PaginatedResponse,
            PaginationParams,
            BaseSearchParams,
        )
        assert BaseResponse is not None
        assert PaginatedResponse is not None
        assert PaginationParams is not None
        assert BaseSearchParams is not None

    def test_total_schema_count(self):
        """Le barrel export charge les schémas actifs (+ ActivityLog)."""
        import backend.api.schemas as s
        response_classes = [
            name for name in dir(s)
            if name.endswith("Response") and not name.startswith("_")
        ]
        assert len(response_classes) >= 18, (
            f"Attendu ≥18 Response, trouvé {len(response_classes)}: {response_classes}"
        )

    def test_enum_values(self):
        """Les 4 enums exposent les valeurs attendues."""
        from backend.api.core.enums import (
            WorkflowStatusEnum, RequestSourceEnum, TaskTypeEnum, TaskStatusEnum,
        )
        assert {e.value for e in WorkflowStatusEnum} == {"draft", "active", "archived"}
        assert {e.value for e in RequestSourceEnum} == {"web", "mobile", "guichet", "telephone", "email", "agent"}
        assert "reassignment" in {e.value for e in TaskTypeEnum}
        assert "in_progress" in {e.value for e in TaskStatusEnum}
