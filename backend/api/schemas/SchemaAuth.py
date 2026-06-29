"""
Schémas Pydantic pour l'authentification JWT.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, EmailStr, validator

from api.schemas.SchemaAccount import AccountResponse


# ── Entrée ────────────────────────────────────────────────────────────────────

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


class RegisterRequest(BaseModel):
    """
    Inscription : données minimales pour créer un compte citoyen.
    Le rôle est forcé à 'user' côté serveur — non modifiable par le client.
    """
    direction_id: Optional[int] = None
    unit_id: Optional[int] = None
    name: str
    firstname: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    password: str
    # `role` volontairement absent — fixé à "user" dans ServiceAccount.register()
    matricule: Optional[str] = None
    job: Optional[str] = None
    is_edg_employee: bool = False

    @validator("password")
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit comporter au moins 8 caractères.")
        return v

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le nom ne peut pas être vide.")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    """Déconnexion : révoque les deux tokens (refresh obligatoire, access optionnel)."""
    refresh_token: str
    access_token: Optional[str] = None  # Si fourni, l'access token est aussi blacklisté


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @validator("new_password")
    def new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le nouveau mot de passe doit comporter au moins 8 caractères.")
        return v


class SetPasswordRequest(BaseModel):
    """Réservé à l'admin pour définir/réinitialiser un mot de passe."""
    password: str

    @validator("password")
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit comporter au moins 8 caractères.")
        return v


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
