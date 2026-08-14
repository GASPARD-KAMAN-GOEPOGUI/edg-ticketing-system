"""
Test 08 — Règles de validation Pydantic (validators, contraintes de types).
Couvre : rating range, EmailStr, champs requis, types incorrects.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas.SchemaAppreciation import (
    AppreciationCreate, AppreciationUpdate,
)
from backend.api.schemas.SchemaAccount import AccountCreate
from backend.api.schemas.SchemaRequest import RequestCreate
from backend.api.schemas.SchemaAttachment import AttachmentCreate
from backend.api.schemas.SchemaSlaPolicy import SlaPolicyCreate


FAKE_ID = "a" * 32


class TestRatingValidator:
    """AppreciationBase.rating_range : valeurs 1–5 uniquement."""

    def test_rating_1_valid(self):
        obj = AppreciationCreate(
            request_id=FAKE_ID, rating=1,
            resolved_confirmed=True, author_type="external",
        )
        assert obj.rating == 1

    def test_rating_5_valid(self):
        obj = AppreciationCreate(
            request_id=FAKE_ID, rating=5,
            resolved_confirmed=True, author_type="external",
        )
        assert obj.rating == 5

    def test_rating_0_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            AppreciationCreate(
                request_id=FAKE_ID, rating=0,
                resolved_confirmed=True, author_type="external",
            )
        assert "rating" in str(exc_info.value).lower() or "entre 1 et 5" in str(exc_info.value)

    def test_rating_6_raises(self):
        with pytest.raises(ValidationError):
            AppreciationCreate(
                request_id=FAKE_ID, rating=6,
                resolved_confirmed=True, author_type="external",
            )

    def test_rating_negative_raises(self):
        with pytest.raises(ValidationError):
            AppreciationCreate(
                request_id=FAKE_ID, rating=-1,
                resolved_confirmed=True, author_type="external",
            )

    def test_update_rating_none_valid(self):
        obj = AppreciationUpdate(rating=None)
        assert obj.rating is None

    def test_update_rating_3_valid(self):
        obj = AppreciationUpdate(rating=3)
        assert obj.rating == 3

    def test_update_rating_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            AppreciationUpdate(rating=10)


class TestEmailValidator:
    """AccountCreate.email : doit être une adresse email valide (EmailStr)."""

    def test_valid_email(self):
        obj = AccountCreate(name="Test", email="valid@edg.gn", password="Password123!")
        assert obj.email == "valid@edg.gn"

    def test_invalid_email_no_at(self):
        with pytest.raises(ValidationError):
            AccountCreate(name="Test", email="notanemail")

    def test_invalid_email_no_domain(self):
        with pytest.raises(ValidationError):
            AccountCreate(name="Test", email="user@")

    def test_invalid_email_no_tld(self):
        with pytest.raises(ValidationError):
            AccountCreate(name="Test", email="user@domain")

    def test_email_with_subdomain_valid(self):
        obj = AccountCreate(name="Test", email="user@mail.edg.gn", password="Password123!")
        assert "edg.gn" in obj.email


class TestRequiredFieldsEnforced:
    """Vérifie que les champs obligatoires déclenchent bien une ValidationError."""

    def test_request_create_all_required(self):
        with pytest.raises(ValidationError) as exc_info:
            RequestCreate()
        errors = exc_info.value.errors()
        required_fields = {e["loc"][0] for e in errors}
        assert "title" in required_fields
        assert "description" in required_fields
        assert "category" in required_fields
        assert "is_external" in required_fields

    def test_attachment_size_bytes_required(self):
        with pytest.raises(ValidationError):
            AttachmentCreate(
                request_id=FAKE_ID,
                filename="f.pdf",
                storage_path="/f.pdf",
                mime_type="application/pdf",
            )

    def test_sla_policy_all_required(self):
        with pytest.raises(ValidationError):
            SlaPolicyCreate()


class TestTypeCoercion:
    """Pydantic v1 coerce les types numériques compatibles."""

    def test_string_to_int_coercion_sla(self):
        obj = SlaPolicyCreate(
            category="cat",
            priority="high",
            response_h="4",
            resolution_h="48",
            escalate_after_h="24",
        )
        assert obj.response_h == 4
        assert isinstance(obj.response_h, int)

    def test_bool_coercion_account(self):
        obj = AccountCreate(name="Test", email="t@edg.gn", password="Password123!", is_edg_employee=1)
        assert obj.is_edg_employee is True


class TestOptionalFields:
    """Les champs Optional peuvent être None ou absents."""

    def test_request_optional_geo_fields(self):
        obj = RequestCreate(
            title="T", description="D", category="C",
            is_external=True, requester_name="J",
        )
        assert obj.lat is None
        assert obj.lng is None
        assert obj.meter_number is None

    def test_account_optional_unity(self):
        obj = AccountCreate(name="User", email="u@edg.gn", password="Password123!")
        assert obj.unity_id is None
