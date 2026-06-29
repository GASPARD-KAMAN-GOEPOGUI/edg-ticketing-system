"""
Test 02 — Schémas de base : BaseResponse, PaginatedResponse, PaginationParams, BaseSearchParams.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.api.schemas.base import (
    BaseResponse,
    BaseSearchParams,
    PaginatedResponse,
    PaginationParams,
)

NOW = datetime(2026, 1, 15, 10, 0, 0)
FAKE_ID = "b" * 32


class TestBaseResponse:
    def _make(self, **kw) -> dict:
        base = {
            "id": FAKE_ID,
            "status": True,
            "infos": None,
            "created_at": NOW,
            "updated_at": NOW,
            "deleted_at": None,
        }
        base.update(kw)
        return base

    def test_valid_minimal(self):
        obj = BaseResponse(**self._make())
        assert obj.id == FAKE_ID
        assert obj.status is True
        assert obj.deleted_at is None

    def test_valid_with_infos(self):
        obj = BaseResponse(**self._make(infos={"key": "val"}))
        assert obj.infos == {"key": "val"}

    def test_valid_soft_deleted(self):
        obj = BaseResponse(**self._make(deleted_at=NOW))
        assert obj.deleted_at == NOW

    def test_missing_id_raises(self):
        data = self._make()
        del data["id"]
        with pytest.raises(ValidationError):
            BaseResponse(**data)

    def test_missing_created_at_raises(self):
        data = self._make()
        del data["created_at"]
        with pytest.raises(ValidationError):
            BaseResponse(**data)

    def test_orm_mode_enabled(self):
        assert BaseResponse.__config__.orm_mode is True


class TestPaginatedResponse:
    def test_valid_paginated(self):
        obj = PaginatedResponse[str](
            items=["a", "b"],
            total=10,
            page=1,
            page_size=2,
            pages=5,
        )
        assert obj.total == 10
        assert len(obj.items) == 2
        assert obj.pages == 5

    def test_empty_items(self):
        obj = PaginatedResponse[str](
            items=[], total=0, page=1, page_size=20, pages=0
        )
        assert obj.items == []
        assert obj.total == 0

    def test_missing_total_raises(self):
        with pytest.raises(ValidationError):
            PaginatedResponse[str](items=[], page=1, page_size=20, pages=0)

    def test_generic_with_dict_items(self):
        items = [{"id": FAKE_ID, "name": "test"}]
        obj = PaginatedResponse[dict](
            items=items, total=1, page=1, page_size=20, pages=1
        )
        assert obj.items[0]["name"] == "test"


class TestPaginationParams:
    def test_defaults(self):
        obj = PaginationParams()
        assert obj.page == 1
        assert obj.page_size == 20

    def test_custom_values(self):
        obj = PaginationParams(page=3, page_size=50)
        assert obj.page == 3
        assert obj.page_size == 50

    def test_offset_page_1(self):
        obj = PaginationParams(page=1, page_size=20)
        assert obj.offset() == 0

    def test_offset_page_3(self):
        obj = PaginationParams(page=3, page_size=20)
        assert obj.offset() == 40

    def test_offset_custom(self):
        obj = PaginationParams(page=5, page_size=10)
        assert obj.offset() == 40


class TestBaseSearchParams:
    def test_defaults(self):
        obj = BaseSearchParams()
        assert obj.q is None
        assert obj.status is None
        assert obj.deleted is False
        assert obj.sort_by == "created_at"
        assert obj.sort_dir == "desc"

    def test_full_params(self):
        obj = BaseSearchParams(
            q="test query",
            status=True,
            deleted=True,
            sort_by="updated_at",
            sort_dir="asc",
        )
        assert obj.q == "test query"
        assert obj.status is True
        assert obj.deleted is True
        assert obj.sort_by == "updated_at"
        assert obj.sort_dir == "asc"

    def test_status_filter_false(self):
        obj = BaseSearchParams(status=False)
        assert obj.status is False
