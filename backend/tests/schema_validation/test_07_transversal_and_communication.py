"""
Test 07 — Schémas transverses et communication :
Notification, ActivityLog, Appreciation.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.SchemaNotification import (
    NotificationCreate, NotificationUpdate, NotificationResponse,
)
from backend.api.schemas.SchemaActivityLog import (
    ActivityLogCreate, ActivityLogResponse,
)
from backend.api.schemas.SchemaAppreciation import (
    AppreciationCreate, AppreciationUpdate, AppreciationResponse,
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


class TestNotification:
    def test_create_valid(self):
        obj = NotificationCreate(
            recipient_id=FAKE_ID,
            title="Votre demande a été traitée",
            body="La demande REQ-001 a été résolue.",
        )
        assert obj.type == "info"
        assert obj.channel == "in_app"

    def test_create_missing_title_raises(self):
        with pytest.raises(ValidationError):
            NotificationCreate(recipient_id=FAKE_ID, body="Body")

    def test_update_read_status(self):
        obj = NotificationUpdate(is_read=True, read_at=NOW)
        assert obj.is_read is True
        assert obj.read_at == NOW

    def test_response_valid(self):
        data = {
            **BASE,
            "recipient_id": FAKE_ID,
            "type": "info",
            "channel": "in_app",
            "title": "Notification",
            "body": "Corps de la notification",
            "is_read": False,
        }
        obj = NotificationResponse(**data)
        assert obj.is_read is False
        assert NotificationResponse.__config__.orm_mode is True

class TestActivityLog:
    def test_create_valid(self):
        obj = ActivityLogCreate(
            actor="gaspard@edg.gn",
            actor_role="admin",
            action="REQUEST_CREATED",
            category="request",
            target="REQ-001",
            log_status="success",
        )
        assert obj.actor_id is None
        assert obj.ip_address is None

    def test_create_full(self):
        obj = ActivityLogCreate(
            actor="gaspard@edg.gn",
            actor_id=FAKE_ID,
            actor_role="admin",
            action="LOGIN",
            category="auth",
            target="account",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            log_status="success",
        )
        assert obj.ip_address == "192.168.1.1"

    def test_create_missing_action_raises(self):
        with pytest.raises(ValidationError):
            ActivityLogCreate(
                actor="user",
                actor_role="admin",
                category="auth",
                target="account",
                log_status="success",
            )

    def test_no_update_class(self):
        import backend.api.schemas.SchemaActivityLog as m
        assert not hasattr(m, "ActivityLogUpdate"), (
            "ActivityLog est append-only — pas de classe Update attendue"
        )

    def test_response_valid(self):
        data = {
            **BASE,
            "actor": "gaspard@edg.gn",
            "actor_role": "admin",
            "action": "LOGIN",
            "category": "auth",
            "target": "account",
            "log_status": "success",
        }
        obj = ActivityLogResponse(**data)
        assert obj.action == "LOGIN"
        assert ActivityLogResponse.__config__.orm_mode is True

class TestAppreciation:
    def test_create_valid(self):
        obj = AppreciationCreate(
            request_id=FAKE_ID,
            rating=4,
            resolved_confirmed=True,
            author_type="external",
        )
        assert obj.rating == 4

    def test_create_missing_rating_raises(self):
        with pytest.raises(ValidationError):
            AppreciationCreate(
                request_id=FAKE_ID,
                resolved_confirmed=True,
                author_type="external",
            )

    def test_update_partial(self):
        obj = AppreciationUpdate(rating=5, comment="Excellent service!")
        assert obj.rating == 5
