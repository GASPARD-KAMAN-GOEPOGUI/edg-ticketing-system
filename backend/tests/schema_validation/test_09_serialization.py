"""
Test 09 — Sérialisation / désérialisation et compatibilité ORM.
Couvre : .dict(), .json(), orm_mode (from_orm), champs imbriqués.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from backend.api.schemas.base import BaseResponse, PaginatedResponse, PaginationParams
from backend.api.schemas.SchemaUnity import UnityResponse
from backend.api.schemas.SchemaAccount import AccountResponse
from backend.api.schemas.SchemaRequest import RequestCreate, RequestResponse
from backend.api.schemas.SchemaAppreciation import AppreciationCreate

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


class TestDictSerialization:
    def test_unity_response_dict(self):
        obj = UnityResponse(**{**BASE, "codename": "DSI", "label": "Direction des Systèmes d'Information"})
        d = obj.dict()
        assert d["codename"] == "DSI"
        assert d["id"] == FAKE_ID
        assert isinstance(d["created_at"], datetime)

    def test_request_create_dict_excludes_none(self):
        obj = RequestCreate(
            title="T", description="D", category="C",
            is_external=True, requester_name="J",
        )
        d = obj.dict(exclude_none=True)
        assert "lat" not in d
        assert "lng" not in d
        assert "title" in d

    def test_request_create_dict_includes_none(self):
        obj = RequestCreate(
            title="T", description="D", category="C",
            is_external=True, requester_name="J",
        )
        d = obj.dict()
        assert "lat" in d
        assert d["lat"] is None


class TestJsonSerialization:
    def test_unity_response_json(self):
        obj = UnityResponse(**{**BASE, "codename": "DSI", "label": "Direction SI"})
        j = obj.json()
        parsed = json.loads(j)
        assert parsed["codename"] == "DSI"
        assert "created_at" in parsed

class TestOrmMode:
    """Simule from_orm via un objet SimpleNamespace (duck-typing)."""

    def test_unity_from_orm(self):
        from types import SimpleNamespace
        orm_obj = SimpleNamespace(
            id=FAKE_ID,
            status=True,
            infos=None,
            created_at=NOW,
            updated_at=NOW,
            deleted_at=None,
            codename="DT",
            label="Direction Technique",
            aleas="DT",
            description=None,
        )
        obj = UnityResponse.from_orm(orm_obj)
        assert obj.codename == "DT"
        assert obj.id == FAKE_ID

    def test_account_from_orm(self):
        from types import SimpleNamespace
        orm_obj = SimpleNamespace(
            id=FAKE_ID,
            status=True,
            infos=None,
            created_at=NOW,
            updated_at=NOW,
            deleted_at=None,
            keycloak_id=None,
            name="Test User",
            email="test@edg.gn",
            role="user",
            account_status="active",
            matricule=None,
            job=None,
            unity_id=None,
            avatar_url=None,
            is_edg_employee=False,
            email_verified=False,
            activated_at=None,
            mfa_enabled=False,
            availability=None,
            notif_sla_alerts=True,
            notif_escalations=True,
            notif_comments=True,
            notif_resolutions=True,
        )
        obj = AccountResponse.from_orm(orm_obj)
        assert obj.role == "user"
        assert obj.email == "test@edg.gn"

    def test_base_response_orm_mode_flag(self):
        assert BaseResponse.__config__.orm_mode is True


class TestPaginationHelpers:
    def test_paginated_response_construction(self):
        items = [
            UnityResponse(**{**BASE, "id": "a" * 32, "codename": "D1", "label": "Dir 1"}),
            UnityResponse(**{**BASE, "id": "b" * 32, "codename": "D2", "label": "Dir 2"}),
        ]
        page = PaginatedResponse[UnityResponse](
            items=items,
            total=50,
            page=2,
            page_size=2,
            pages=25,
        )
        assert page.total == 50
        assert page.pages == 25
        assert page.items[0].codename == "D1"

    def test_pagination_params_offset_calculation(self):
        cases = [
            (PaginationParams(page=1, page_size=20), 0),
            (PaginationParams(page=2, page_size=20), 20),
            (PaginationParams(page=3, page_size=10), 20),
            (PaginationParams(page=10, page_size=5), 45),
        ]
        for params, expected_offset in cases:
            assert params.offset() == expected_offset, (
                f"page={params.page}, page_size={params.page_size} → "
                f"offset attendu {expected_offset}, obtenu {params.offset()}"
            )

    def test_pagination_json_serializable(self):
        page = PaginatedResponse[str](
            items=["a", "b"],
            total=2,
            page=1,
            page_size=10,
            pages=1,
        )
        j = page.json()
        parsed = json.loads(j)
        assert parsed["total"] == 2
        assert parsed["items"] == ["a", "b"]


