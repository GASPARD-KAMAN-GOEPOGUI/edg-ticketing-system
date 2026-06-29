"""
Test 05 — Chaîne Request et ses enfants :
Request, WorkflowDetail (timeline), Attachment, SmsLog.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.SchemaRequest import (
    RequestBase, RequestCreate, RequestUpdate, RequestResponse,
)
from backend.api.schemas.SchemaWorkflowDetail import (
    WorkflowDetailCreate, WorkflowDetailUpdate, WorkflowDetailResponse,
)
from backend.api.schemas.SchemaAttachment import (
    AttachmentCreate, AttachmentUpdate, AttachmentResponse,
)
from backend.api.schemas.SchemaSmsLog import (
    SmsLogCreate, SmsLogUpdate, SmsLogResponse,
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


class TestRequest:
    def _create_payload(self, **kw) -> dict:
        base = {
            "title": "Demande de raccordement",
            "description": "Description de la demande",
            "category": "raccordement",
            "is_external": True,
            "requester_name": "John Doe",
        }
        base.update(kw)
        return base

    def test_create_valid_external(self):
        obj = RequestCreate(**self._create_payload())
        assert obj.title == "Demande de raccordement"
        assert obj.is_external is True
        assert obj.submission_mode == "personal"
        assert obj.request_status == "new"

    def test_create_valid_internal(self):
        obj = RequestCreate(**self._create_payload(
            is_external=False,
            requester_id=FAKE_ID,
            employee_matricule="MAT001",
        ))
        assert obj.requester_id == FAKE_ID

    def test_create_missing_title_raises(self):
        with pytest.raises(ValidationError):
            RequestCreate(
                description="desc", category="cat",
                is_external=True, requester_name="John",
            )

    def test_create_missing_description_raises(self):
        with pytest.raises(ValidationError):
            RequestCreate(
                title="title", category="cat",
                is_external=True, requester_name="John",
            )

    def test_update_partial(self):
        obj = RequestUpdate(request_status="in_progress", priority="high")
        assert obj.request_status == "in_progress"
        assert obj.title is None

    def test_update_sla_fields(self):
        obj = RequestUpdate(sla_hours=24, sla_breached=False)
        assert obj.sla_hours == 24

    def test_response_valid(self):
        data = {
            **BASE,
            "ref": "REQ-2026-001",
            "title": "Raccordement",
            "description": "Desc",
            "request_status": "new",
            "priority": "medium",
            "category": "raccordement",
            "in_triage": False,
            "is_external": True,
            "submission_mode": "personal",
            "requester_name": "John Doe",
            "sla_hours": 48,
            "sla_elapsed": 0,
            "sla_breached": False,
        }
        obj = RequestResponse(**data)
        assert obj.ref == "REQ-2026-001"
        assert RequestResponse.__config__.orm_mode is True

    def test_response_optional_fields_null(self):
        data = {
            **BASE,
            "ref": "REQ-001",
            "title": "T",
            "description": "D",
            "request_status": "new",
            "priority": "medium",
            "category": "cat",
            "in_triage": False,
            "is_external": False,
            "submission_mode": "personal",
            "requester_name": "",
            "sla_hours": 24,
            "sla_elapsed": 0,
            "sla_breached": False,
        }
        obj = RequestResponse(**data)
        assert obj.unity_id is None
        assert obj.requester_phone is None


class TestWorkflowDetailTimeline:
    def test_create_event_valid(self):
        obj = WorkflowDetailCreate(
            request_id=1,
            event_type="status_change",
            label="Statut changé en cours",
            activated=False,
        )
        assert obj.event_type == "status_change"
        assert obj.accepted is None

    def test_create_step_valid(self):
        obj = WorkflowDetailCreate(
            workflow_id=1,
            agent_id=42,
            activated=True,
        )
        assert obj.activated is True
        assert obj.workflow_id == 1

    def test_update_partial(self):
        obj = WorkflowDetailUpdate(label="Nouveau label")
        assert obj.label == "Nouveau label"

    def test_update_accept(self):
        obj = WorkflowDetailUpdate(accepted=True, comment="OK validé")
        assert obj.accepted is True

    def test_response_valid(self):
        data = {
            **BASE,
            "request_id": 1,
            "event_type": "status_change",
            "label": "Statut changé",
            "activated": False,
        }
        obj = WorkflowDetailResponse(**data)
        assert obj.event_type == "status_change"
        assert obj.accepted is None
        assert WorkflowDetailResponse.__config__.orm_mode is True


class TestAttachment:
    def test_create_valid(self):
        obj = AttachmentCreate(
            request_id=FAKE_ID,
            filename="facture.pdf",
            storage_path="/files/facture.pdf",
            mime_type="application/pdf",
            size_bytes=102400,
        )
        assert obj.scan_status == "pending_scan"
        assert obj.uploader_id is None

    def test_create_with_uploader(self):
        obj = AttachmentCreate(
            request_id=FAKE_ID,
            uploader_id=FAKE_ID,
            filename="photo.jpg",
            storage_path="/files/photo.jpg",
            mime_type="image/jpeg",
            size_bytes=512000,
        )
        assert obj.uploader_id == FAKE_ID

    def test_create_missing_filename_raises(self):
        with pytest.raises(ValidationError):
            AttachmentCreate(
                request_id=FAKE_ID,
                storage_path="/f",
                mime_type="application/pdf",
                size_bytes=100,
            )

    def test_update_scan_status(self):
        obj = AttachmentUpdate(clamav_clean=True, scan_status="clean")
        assert obj.clamav_clean is True

    def test_response_valid(self):
        data = {
            **BASE,
            "request_id": FAKE_ID,
            "filename": "doc.pdf",
            "storage_path": "/files/doc.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "scan_status": "clean",
        }
        obj = AttachmentResponse(**data)
        assert obj.scan_status == "clean"
        assert AttachmentResponse.__config__.orm_mode is True


class TestSmsLog:
    def test_create_valid(self):
        obj = SmsLogCreate(
            request_id=FAKE_ID,
            event="submission",
            phone="+224620000000",
        )
        assert obj.delivery_status == "sent"

    def test_update_delivery_status(self):
        obj = SmsLogUpdate(delivery_status="delivered")
        assert obj.delivery_status == "delivered"

    def test_response_valid(self):
        data = {
            **BASE,
            "request_id": FAKE_ID,
            "event": "submission",
            "phone": "+224620000000",
            "sent_at": NOW,
            "delivery_status": "sent",
        }
        obj = SmsLogResponse(**data)
        assert obj.phone == "+224620000000"
        assert SmsLogResponse.__config__.orm_mode is True


