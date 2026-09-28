"""
Test 03 — Tables de référence dynamiques (8 tables).
workflow_status, request_source, task_type, task_status → enums (api.core.enums).
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.SchemaRequestStatus import (
    RequestStatusCreate, RequestStatusUpdate, RequestStatusResponse,
)
from backend.api.schemas.SchemaPriorityDefinition import (
    PriorityDefinitionCreate, PriorityDefinitionUpdate, PriorityDefinitionResponse,
)

NOW = datetime(2026, 1, 15, 10, 0, 0)
FAKE_ID = "c" * 32

BASE_RESPONSE = {
    "id": FAKE_ID,
    "status": True,
    "infos": None,
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": None,
}

# Payload commun aux tables code/label/sort_order/is_builtin
def _ref_create(code: str = "test", label: str = "Test") -> dict:
    return {"code": code, "label": label}

def _ref_response(code: str = "test", label: str = "Test") -> dict:
    return {**BASE_RESPONSE, "code": code, "label": label, "sort_order": 0, "is_builtin": False}


class TestRequestStatus:
    def test_create_valid(self):
        obj = RequestStatusCreate(**_ref_create("new", "Nouvelle"))
        assert obj.code == "new"

    def test_create_defaults(self):
        obj = RequestStatusCreate(code="new", label="Nouvelle")
        assert obj.sort_order == 0
        assert obj.is_builtin is False

    def test_update_partial(self):
        obj = RequestStatusUpdate(label="Mise à jour")
        assert obj.label == "Mise à jour"
        assert obj.code is None

    def test_response_valid(self):
        obj = RequestStatusResponse(**_ref_response("new", "Nouvelle"))
        assert obj.code == "new"
        assert RequestStatusResponse.__config__.orm_mode is True

    def test_create_missing_code_raises(self):
        with pytest.raises(ValidationError):
            RequestStatusCreate(label="Nouvelle")

    def test_create_missing_label_raises(self):
        with pytest.raises(ValidationError):
            RequestStatusCreate(code="new")

class TestPriorityDefinition:
    def test_create_valid(self):
        obj = PriorityDefinitionCreate(
            slug="urgent", label="Urgent", sort_order=1
        )
        assert obj.slug == "urgent"
        assert obj.sort_order == 1
        assert obj.color == "slate"  # default

    def test_create_missing_slug_raises(self):
        with pytest.raises(ValidationError):
            PriorityDefinitionCreate(label="Urgent", sort_order=1)

    def test_create_missing_sort_order_raises(self):
        with pytest.raises(ValidationError):
            PriorityDefinitionCreate(slug="urgent", label="Urgent")

    def test_response_valid(self):
        data = {
            **BASE_RESPONSE,
            "slug": "urgent",
            "label": "Urgent",
            "description": "",
            "color": "red",
            "sort_order": 1,
            "is_builtin": False,
        }
        obj = PriorityDefinitionResponse(**data)
        assert obj.color == "red"
        assert PriorityDefinitionResponse.__config__.orm_mode is True
