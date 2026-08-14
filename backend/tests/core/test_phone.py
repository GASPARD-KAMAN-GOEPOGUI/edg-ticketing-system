"""Tests unitaires — validation des numéros de téléphone guinéens (core/phone.py)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.core.phone import validate_guinea_phone


class TestValidateGuineaPhoneAccepte:
    @pytest.mark.parametrize("raw", [
        "+224 620 12 34 56",
        "224 620 12 34 56",
        "620 12 34 56",
        "+224620123456",
        "224620123456",
        "620123456",
    ])
    def test_formats_valides_normalises_en_e164(self, raw):
        assert validate_guinea_phone(raw) == "+224620123456"

    def test_champ_vide_ou_none_retourne_none(self):
        assert validate_guinea_phone(None) is None
        assert validate_guinea_phone("") is None
        assert validate_guinea_phone("   ") is None


class TestValidateGuineaPhoneRejette:
    @pytest.mark.parametrize("raw", [
        "+224 520 12 34 56",   # ne commence pas par 6 (prefixe mobile)
        "620 12 34",            # trop court
        "620 12 34 56 78",      # trop long
        "+224 62012345",        # 8 chiffres locaux au lieu de 9
        "abcdefghi",             # pas un numero
    ])
    def test_formats_invalides_levent_value_error(self, raw):
        with pytest.raises(ValueError):
            validate_guinea_phone(raw)


class TestSchemasRejettentTelephoneInvalide:
    """
    Vérifie le câblage de validate_guinea_phone() dans les schémas Pydantic —
    sans passer par HTTP (évite le rate-limiter de /auth/register en test).
    """

    def test_register_request_rejette_telephone_invalide(self):
        from api.schemas.SchemaAuth import RegisterRequest
        with pytest.raises(ValidationError):
            RegisterRequest(name="Test", email="x@test.edg.gn", password="Password123!", phone="123456")

    def test_register_request_normalise_telephone_valide(self):
        from api.schemas.SchemaAuth import RegisterRequest
        req = RegisterRequest(name="Test", email="x@test.edg.gn", password="Password123!", phone="620 12 34 56")
        assert req.phone == "+224620123456"

    def test_account_update_rejette_telephone_invalide(self):
        from api.schemas.SchemaAccount import AccountUpdate
        with pytest.raises(ValidationError):
            AccountUpdate(phone="123456")

    def test_account_update_normalise_telephone_valide(self):
        from api.schemas.SchemaAccount import AccountUpdate
        upd = AccountUpdate(phone="224 620 12 34 56")
        assert upd.phone == "+224620123456"
