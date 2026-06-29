"""
Test 06 — Configuration et Workflow :
Category, SlaPolicy, RoutingRule, Workflow, WorkflowDetail, Task.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.SchemaCategory import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
)
from backend.api.schemas.SchemaSlaPolicy import (
    SlaPolicyCreate, SlaPolicyUpdate, SlaPolicyResponse,
)
from backend.api.schemas.SchemaRoutingRule import (
    RoutingRuleCreate, RoutingRuleUpdate, RoutingRuleResponse,
)
from backend.api.schemas.SchemaWorkflow import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse,
)
from backend.api.schemas.SchemaWorkflowDetail import (
    WorkflowDetailCreate, WorkflowDetailUpdate, WorkflowDetailResponse,
)
from backend.api.schemas.SchemaTask import (
    TaskCreate, TaskUpdate, TaskResponse,
)

NOW = datetime(2026, 1, 15, 10, 0, 0)
FAKE_ID = "a" * 32

BASE = {
    "id": FAKE_ID,
    "status": True,
    "infos": None,
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": None,
}


class TestCategory:
    def test_create_valid(self):
        obj = CategoryCreate(name="Raccordement")
        assert obj.name == "Raccordement"
        assert obj.target_type == "both"

    def test_create_with_defaults(self):
        obj = CategoryCreate(name="Facturation", target_type="external")
        assert obj.target_type == "external"

    def test_create_missing_name_raises(self):
        with pytest.raises(ValidationError):
            CategoryCreate()

    def test_update_partial(self):
        obj = CategoryUpdate(name="Nouveau nom")
        assert obj.name == "Nouveau nom"
        assert obj.target_type is None

    def test_response_valid(self):
        data = {**BASE, "name": "Raccordement", "target_type": "both"}
        obj = CategoryResponse(**data)
        assert obj.name == "Raccordement"
        assert CategoryResponse.__config__.orm_mode is True


class TestSlaPolicy:
    def test_create_valid(self):
        obj = SlaPolicyCreate(
            category="raccordement",
            priority="high",
            response_h=4,
            resolution_h=48,
            escalate_after_h=24,
        )
        assert obj.response_h == 4

    def test_create_missing_category_raises(self):
        with pytest.raises(ValidationError):
            SlaPolicyCreate(priority="high", response_h=4, resolution_h=48, escalate_after_h=24)

    def test_update_partial(self):
        obj = SlaPolicyUpdate(escalate_after_h=12)
        assert obj.escalate_after_h == 12
        assert obj.response_h is None

    def test_response_valid(self):
        data = {
            **BASE,
            "category": "raccordement",
            "priority": "high",
            "response_h": 4,
            "resolution_h": 48,
            "escalate_after_h": 24,
        }
        obj = SlaPolicyResponse(**data)
        assert obj.resolution_h == 48
        assert SlaPolicyResponse.__config__.orm_mode is True


class TestRoutingRule:
    def test_create_valid(self):
        obj = RoutingRuleCreate(
            name="Règle site résidentiel",
            condition_field="site_type",
            condition_value="residential",
            sort_order=1,
        )
        assert obj.auto_assign is False

    def test_create_with_target(self):
        obj = RoutingRuleCreate(
            name="Règle DG",
            condition_field="category",
            condition_value="raccordement",
            target_unity_id=FAKE_ID,
            auto_assign=True,
            sort_order=2,
        )
        assert obj.target_unity_id == FAKE_ID

    def test_create_missing_name_raises(self):
        with pytest.raises(ValidationError):
            RoutingRuleCreate(condition_field="site_type", condition_value="x", sort_order=1)

    def test_update_partial(self):
        obj = RoutingRuleUpdate(auto_assign=True)
        assert obj.auto_assign is True
        assert obj.name is None

    def test_response_valid(self):
        data = {
            **BASE,
            "name": "Règle 1",
            "condition_field": "site_type",
            "condition_value": "residential",
            "auto_assign": False,
            "sort_order": 1,
        }
        obj = RoutingRuleResponse(**data)
        assert obj.sort_order == 1
        assert RoutingRuleResponse.__config__.orm_mode is True


class TestWorkflow:
    def test_create_valid(self):
        obj = WorkflowCreate(request_id=FAKE_ID)
        assert obj.workflow_status == "active"

    def test_create_custom_status(self):
        obj = WorkflowCreate(request_id=FAKE_ID, workflow_status="completed")
        assert obj.workflow_status == "completed"

    def test_create_missing_request_id_raises(self):
        with pytest.raises(ValidationError):
            WorkflowCreate()

    def test_update_partial(self):
        obj = WorkflowUpdate(workflow_status="suspended")
        assert obj.workflow_status == "suspended"

    def test_response_valid(self):
        data = {**BASE, "request_id": FAKE_ID, "workflow_status": "active"}
        obj = WorkflowResponse(**data)
        assert obj.workflow_status == "active"
        assert WorkflowResponse.__config__.orm_mode is True


class TestWorkflowDetail:
    def test_create_valid(self):
        obj = WorkflowDetailCreate(workflow_id=FAKE_ID)
        assert obj.accepted is False
        assert obj.activated is False
        assert obj.workflow_status == "active"

    def test_create_with_parent(self):
        parent_id = "b" * 32
        obj = WorkflowDetailCreate(
            workflow_id=FAKE_ID,
            parent_id=parent_id,
            agent_id=FAKE_ID,
        )
        assert obj.parent_id == parent_id

    def test_create_missing_workflow_id_raises(self):
        with pytest.raises(ValidationError):
            WorkflowDetailCreate()

    def test_update_acceptance(self):
        obj = WorkflowDetailUpdate(accepted=True, activated=True)
        assert obj.accepted is True

    def test_response_valid(self):
        data = {
            **BASE,
            "workflow_id": FAKE_ID,
            "accepted": False,
            "activated": False,
            "workflow_status": "active",
        }
        obj = WorkflowDetailResponse(**data)
        assert obj.unity_id is None
        assert WorkflowDetailResponse.__config__.orm_mode is True


class TestTask:
    def test_create_valid(self):
        obj = TaskCreate(task_type="transfer", request_id=FAKE_ID)
        assert obj.task_status == "pending"

    def test_create_full(self):
        obj = TaskCreate(
            task_type="assignment",
            request_id=FAKE_ID,
            workflow_id=FAKE_ID,
            from_agent_id=FAKE_ID,
            to_agent_id=FAKE_ID,
            reason="Transfert de compétence",
        )
        assert obj.reason == "Transfert de compétence"

    def test_create_missing_task_type_raises(self):
        with pytest.raises(ValidationError):
            TaskCreate(request_id=FAKE_ID)

    def test_update_partial(self):
        obj = TaskUpdate(task_status="completed")
        assert obj.task_status == "completed"
        assert obj.to_agent_id is None

    def test_response_valid(self):
        data = {
            **BASE,
            "task_type": "transfer",
            "request_id": FAKE_ID,
            "task_status": "pending",
        }
        obj = TaskResponse(**data)
        assert obj.task_type == "transfer"
        assert TaskResponse.__config__.orm_mode is True
