"""
Test 07 — Schémas transverses et communication :
Notification, KnowledgeArticle, ActivityLog,
Announcement + ses sous-tables, CommunicationSetting, Appreciation.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.SchemaNotification import (
    NotificationCreate, NotificationUpdate, NotificationResponse,
)
from backend.api.schemas.SchemaKnowledgeArticle import (
    KnowledgeArticleCreate, KnowledgeArticleUpdate, KnowledgeArticleResponse,
)
from backend.api.schemas.SchemaActivityLog import (
    ActivityLogCreate, ActivityLogResponse,
)
from backend.api.schemas.SchemaAnnouncement import (
    AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
)
from backend.api.schemas.SchemaAnnouncementTargetRole import (
    AnnouncementTargetRoleCreate, AnnouncementTargetRoleUpdate, AnnouncementTargetRoleResponse,
)
from backend.api.schemas.SchemaCommunicationSetting import (
    CommunicationSettingCreate, CommunicationSettingUpdate, CommunicationSettingResponse,
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


class TestKnowledgeArticle:
    def test_create_valid(self):
        obj = KnowledgeArticleCreate(
            title="Comment faire une demande",
            excerpt="Guide rapide",
            body="Corps de l'article...",
            category="guide",
            author="Admin EDG",
        )
        assert obj.is_published is False
        assert obj.read_time == 3

    def test_create_with_tags(self):
        obj = KnowledgeArticleCreate(
            title="Titre",
            excerpt="Extrait",
            body="Corps",
            category="faq",
            author="Admin",
            tags=["raccordement", "client"],
        )
        assert obj.tags == ["raccordement", "client"]

    def test_update_publish(self):
        obj = KnowledgeArticleUpdate(is_published=True, published_at=NOW)
        assert obj.is_published is True

    def test_response_valid(self):
        data = {
            **BASE,
            "title": "Guide",
            "excerpt": "Extrait",
            "body": "Corps",
            "category": "guide",
            "read_time": 5,
            "author": "Admin",
            "is_published": True,
            "is_archived": False,
        }
        obj = KnowledgeArticleResponse(**data)
        assert obj.is_published is True
        assert KnowledgeArticleResponse.__config__.orm_mode is True


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


class TestAnnouncement:
    def _payload(self, **kw) -> dict:
        base = {
            "title": "Maintenance réseau",
            "description": "Interruption de service prévue",
            "announcement_category": "maintenance",
            "author_id": FAKE_ID,
        }
        base.update(kw)
        return base

    def test_create_valid(self):
        obj = AnnouncementCreate(**self._payload())
        assert obj.announcement_status == "draft"
        assert obj.audience == "internal"

    def test_create_missing_title_raises(self):
        with pytest.raises(ValidationError):
            AnnouncementCreate(
                description="Desc",
                announcement_category="info",
                author_id=FAKE_ID,
            )

    def test_update_partial(self):
        obj = AnnouncementUpdate(announcement_status="published")
        assert obj.announcement_status == "published"

    def test_response_valid(self):
        data = {
            **BASE,
            "title": "Maintenance",
            "description": "Desc",
            "announcement_category": "maintenance",
            "announcement_priority": "normal",
            "announcement_status": "published",
            "audience": "internal",
            "published_at": NOW,
            "author_id": FAKE_ID,
        }
        obj = AnnouncementResponse(**data)
        assert obj.announcement_status == "published"
        assert AnnouncementResponse.__config__.orm_mode is True


class TestAnnouncementTargetRole:
    def test_create_valid(self):
        obj = AnnouncementTargetRoleCreate(announcement_id=FAKE_ID, role="agent")
        assert obj.role == "agent"

    def test_response_valid(self):
        data = {**BASE, "announcement_id": FAKE_ID, "role": "admin"}
        obj = AnnouncementTargetRoleResponse(**data)
        assert obj.role == "admin"


class TestCommunicationSetting:
    def test_create_defaults(self):
        obj = CommunicationSettingCreate()
        assert obj.email_on is True
        assert obj.sms_on is True
        assert obj.whatsapp_on is False

    def test_update_toggle(self):
        obj = CommunicationSettingUpdate(sms_on=False)
        assert obj.sms_on is False
        assert obj.email_on is None

    def test_response_valid(self):
        data = {
            **BASE,
            "internal_notif_on": True,
            "email_on": True,
            "sms_on": True,
            "banner_on": True,
            "whatsapp_on": False,
            "push_mobile_on": False,
            "sender_email": "noreply@edg.gn",
            "sender_sms": "EDG",
            "reply_to": "support@edg.gn",
        }
        obj = CommunicationSettingResponse(**data)
        assert obj.sender_email == "noreply@edg.gn"
        assert CommunicationSettingResponse.__config__.orm_mode is True


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
