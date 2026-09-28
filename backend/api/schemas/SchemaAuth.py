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


class ChangePasswordRequest(BaseModel):
    """Changement de mot de passe depuis l'espace connecté (page Profil).

    Aucun email, aucun code OTP : l'utilisateur est deja authentifie, il saisit
    simplement son nouveau mot de passe et sa confirmation. Le mot de passe n'est
    stocke que par la plateforme centrale — la mise a jour y est donc immediate
    et vaut pour toutes les applications qui en dependent.
    """
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

    @validator("confirm_password")
    def _passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Les deux mots de passe ne correspondent pas.")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    """Déconnexion — plus de révocation locale (tokens émis par le central)."""
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None


class ConsentAcceptRequest(BaseModel):
    """
    Rattachement après consentement — utilisateur authentifié par le central mais
    sans groupe support de cette application (voir POST /auth/login ->
    ConsentRequiredResponse). refresh_token/expires_in sont ré-échoués tels quels
    depuis cette réponse : le bearer central obtenu au login reste valide, pas de
    nouvel appel central_login nécessaire ici.
    """
    refresh_token: str
    expires_in: int
    consent_version: str
    name: str
    firstname: Optional[str] = None
    phone: Optional[str] = None

    @validator("name")
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le nom ne peut pas être vide.")
        return v

    @validator("phone")
    def _validate_phone(cls, v):
        return validate_guinea_phone(v)


# ── Sortie ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Réponse d'authentification complète."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # secondes avant expiration de l'access token
    user: AccountResponse


class ConsentRequiredResponse(BaseModel):
    """
    Retournée par POST /auth/login (200, PAS 401) quand l'authentification
    centrale a réussi mais qu'aucun compte local n'est rattaché ET que
    l'utilisateur n'appartient à aucun groupe support de cette application
    (admin-support/qualify-support/collaborateur-support) — voir
    dependencies.py::resolve_or_provision_login_account. access_token/
    refresh_token/expires_in sont le bearer central déjà valide, à réutiliser
    tel quel pour POST /auth/consent/accept une fois le consentement donné.
    """
    needs_consent: bool = True
    access_token: str
    refresh_token: str
    expires_in: int
    email: str
    suggested_name: Optional[str] = None
    suggested_firstname: Optional[str] = None
    suggested_phone: Optional[str] = None
    consent_version: str


class AccessTokenResponse(BaseModel):
    """Réponse de rafraîchissement du token d'accès."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
