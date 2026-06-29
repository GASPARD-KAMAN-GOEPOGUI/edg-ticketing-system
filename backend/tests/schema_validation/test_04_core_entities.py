"""
Test 04 — Entités métier principales : Unity, Organigram, Account, EmployeeDirectory.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.SchemaUnity import (
    UnityBase, UnityCreate, UnityUpdate, UnityResponse,
)
from backend.api.schemas.SchemaOrganigram import (
    OrganigramBase, OrganigramCreate, OrganigramUpdate, OrganigramResponse,
)
from backend.api.schemas.SchemaAccount import (
    AccountBase, AccountCreate, AccountUpdate, AccountResponse,
)
from backend.api.schemas.SchemaEmployeeDirectory import (
    EmployeeDirectoryBase, EmployeeDirectoryCreate,
    EmployeeDirectoryUpdate, EmployeeDirectoryResponse,
)

NOW = datetime(2026, 1, 15, 10, 0, 0)
FAKE_ID = "d" * 32
DIR_ID = "e" * 32
UNIT_ID = "f" * 32

BASE = {
    "id": FAKE_ID,
    "status": True,
    "infos": None,
    "created_at": NOW,
    "updated_at": NOW,
    "deleted_at": None,
}


class TestUnity:
    def test_create_valid(self):
        obj = UnityCreate(codename="DSI", label="Direction des Systèmes d'Information")
        assert obj.codename == "DSI"
        assert obj.label == "Direction des Systèmes d'Information"

    def test_create_with_aleas(self):
        obj = UnityCreate(codename="DSI", label="Direction SI", aleas="DSI", description="Test")
        assert obj.aleas == "DSI"
        assert obj.description == "Test"

    def test_create_missing_codename_raises(self):
        with pytest.raises(ValidationError):
            UnityCreate(label="Direction Générale")

    def test_create_missing_label_raises(self):
        with pytest.raises(ValidationError):
            UnityCreate(codename="DG")

    def test_update_partial(self):
        obj = UnityUpdate(label="Nouvelle direction")
        assert obj.label == "Nouvelle direction"
        assert obj.codename is None

    def test_update_all_none_valid(self):
        obj = UnityUpdate()
        assert obj.codename is None
        assert obj.label is None

    def test_response_valid(self):
        obj = UnityResponse(**{**BASE, "codename": "DG", "label": "Direction Générale"})
        assert obj.codename == "DG"
        assert UnityResponse.__config__.orm_mode is True

    def test_response_inherits_base_fields(self):
        obj = UnityResponse(**{**BASE, "codename": "DG", "label": "Dir Gen"})
        assert obj.id == FAKE_ID
        assert obj.created_at == NOW


class TestOrganigram:
    def test_create_valid(self):
        obj = OrganigramCreate(unity_id=1)
        assert obj.unity_id == 1
        assert obj.parent_id is None

    def test_create_with_parent(self):
        obj = OrganigramCreate(unity_id=2, parent_id=1)
        assert obj.parent_id == 1

    def test_create_missing_unity_id_raises(self):
        with pytest.raises(ValidationError):
            OrganigramCreate()

    def test_update_partial(self):
        obj = OrganigramUpdate(parent_id=5)
        assert obj.parent_id == 5


class TestAccount:
    def _create_payload(self, **kw) -> dict:
        base = {
            "name": "Gaspard Kamango",
            "email": "gaspard@edg.gn",
            "role": "admin",
        }
        base.update(kw)
        return base

    def test_create_valid(self):
        obj = AccountCreate(**self._create_payload())
        assert obj.email == "gaspard@edg.gn"
        assert obj.role == "admin"

    def test_create_defaults(self):
        obj = AccountCreate(name="Test User", email="test@edg.gn")
        assert obj.role == "user"
        assert obj.is_edg_employee is False
        assert obj.notif_sla_alerts is True

    def test_create_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            AccountCreate(name="Test", email="not-an-email")

    def test_create_missing_name_raises(self):
        with pytest.raises(ValidationError):
            AccountCreate(email="test@edg.gn")

    def test_create_missing_email_raises(self):
        with pytest.raises(ValidationError):
            AccountCreate(name="Test User")

    def test_update_partial(self):
        obj = AccountUpdate(role="manager", availability="busy")
        assert obj.role == "manager"
        assert obj.availability == "busy"
        assert obj.name is None

    def test_response_valid(self):
        data = {
            **BASE,
            "name": "Gaspard",
            "email": "g@edg.gn",
            "role": "admin",
            "account_status": "active",
            "is_edg_employee": True,
            "email_verified": False,
            "mfa_enabled": False,
            "notif_sla_alerts": True,
            "notif_escalations": True,
            "notif_comments": True,
            "notif_resolutions": True,
        }
        obj = AccountResponse(**data)
        assert obj.role == "admin"
        assert AccountResponse.__config__.orm_mode is True

    def test_response_optional_fields_absent(self):
        data = {
            **BASE,
            "name": "Gaspard",
            "email": "g@edg.gn",
            "role": "user",
            "account_status": "active",
            "is_edg_employee": False,
            "email_verified": False,
            "mfa_enabled": False,
            "notif_sla_alerts": True,
            "notif_escalations": True,
            "notif_comments": True,
            "notif_resolutions": True,
        }
        obj = AccountResponse(**data)
        assert obj.unity_id is None
        assert obj.avatar_url is None


class TestEmployeeDirectory:
    def test_create_valid(self):
        obj = EmployeeDirectoryCreate(
            matricule="MAT001",
            email_pro="emp@edg.gn",
            name="Jean Dupont",
        )
        assert obj.matricule == "MAT001"

    def test_create_with_fields(self):
        obj = EmployeeDirectoryCreate(
            matricule="MAT002",
            email_pro="emp2@edg.gn",
            name="Marie Dupont",
            job="Ingénieur",
        )
        assert obj.matricule == "MAT002"

    def test_create_missing_matricule_raises(self):
        with pytest.raises(ValidationError):
            EmployeeDirectoryCreate(email_pro="e@edg.gn", name="Test")

    def test_update_partial(self):
        obj = EmployeeDirectoryUpdate(job="Chef de projet")
        assert obj.job == "Chef de projet"
        assert obj.name is None

    def test_response_valid(self):
        data = {
            **BASE,
            "matricule": "MAT001",
            "email_pro": "emp@edg.gn",
            "name": "Jean Dupont",
        }
        obj = EmployeeDirectoryResponse(**data)
        assert obj.matricule == "MAT001"
        assert EmployeeDirectoryResponse.__config__.orm_mode is True
