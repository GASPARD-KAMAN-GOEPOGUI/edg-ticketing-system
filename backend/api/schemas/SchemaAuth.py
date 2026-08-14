"""
Schémas Pydantic pour l'authentification centrale (manager-user).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator

from api.core.phone import validate_guinea_phone
from api.schemas.SchemaAccount import AccountResponse


# ── Entrée ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Inscription publique — le rôle est toujours forcé à 'user' côté serveur (jamais accepté ici)."""
    name: str
    firstname: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    password: str = Field(..., min_length=8)

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le nom ne peut pas être vide.")
        return v

    @validator("phone")
    def _validate_phone(cls, v):
        return validate_guinea_phone(v)


class LoginRequest(BaseModel):
    """Connexion : email ou matricule + mot de passe."""
    identifier: str        # email ou matricule
    password: str
    device_name: Optional[str] = None  # ex: "Chrome / Windows 11" (optionnel)

    @validator("identifier")
    def identifier_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("L'identifiant ne peut pas être vide.")
        return v

    @validator("password")
    def password_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("Le mot de passe ne peut pas être vide.")
        return v


class ForgotPasswordRequest(BaseModel):
    """Étape 1 — demande d'envoi du code de vérification par email."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Étape 3 — code reçu + nouveau mot de passe."""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    """Déconnexion — plus de révocation locale (tokens émis par le central)."""
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None


# ── Sortie ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Réponse d'authentification complète."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # secondes avant expiration de l'access token
    user: AccountResponse


class AccessTokenResponse(BaseModel):
    """Réponse de rafraîchissement du token d'accès."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
