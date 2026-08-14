from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, root_validator, validator

from api.core.phone import validate_guinea_phone
from api.core.rbac import normalize_role

from .base import BaseResponse


class AccountBase(BaseModel):
    unity_id: Optional[int] = None
    name: str
    firstname: Optional[str] = None
    email: EmailStr
    phone: Optional[str] = None
    role: str = "user"
    account_status: str = "active"
    matricule: Optional[str] = None
    job: Optional[str] = None
    avatar_url: Optional[str] = None
    is_edg_employee: bool = False
    availability: Optional[str] = None
    notif_sla_alerts: bool = True
    notif_escalations: bool = True
    notif_comments: bool = True
    notif_resolutions: bool = True

    @validator("role", pre=True, always=True)
    def _normalize_role(cls, v):
        return normalize_role(v)

    @validator("phone")
    def _validate_phone(cls, v):
        return validate_guinea_phone(v)


class AccountCreate(AccountBase):
    password: str = Field(..., min_length=8, description="Mot de passe initial — transmis à la plateforme centrale à la création.")
    unit_id: Optional[int] = None       # alias frontend pour unity_id
    department_id: Optional[int] = None # alias formulaire admin pour unity_id
    direction_id: Optional[int] = None  # alias formulaire admin pour unity_id
    infos: Optional[Any] = None

    @root_validator(pre=True)
    def _alias_org_assignment(cls, values):
        if values.get("unity_id") is None:
            if values.get("unit_id") is not None:
                values["unity_id"] = values.get("unit_id")
            elif values.get("department_id") is not None:
                values["unity_id"] = values.get("department_id")
            elif values.get("direction_id") is not None:
                values["unity_id"] = values.get("direction_id")
        return values


class AccountUpdate(BaseModel):
    unity_id: Optional[int] = None
    unit_id: Optional[int] = None      # alias frontend pour unity_id
    department_id: Optional[int] = None # alias formulaire admin pour unity_id
    direction_id: Optional[int] = None # ignoré (pas de colonne), accepté pour compatibilité
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    firstname: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    account_status: Optional[str] = None
    matricule: Optional[str] = None
    job: Optional[str] = None
    avatar_url: Optional[str] = None
    is_edg_employee: Optional[bool] = None
    availability: Optional[str] = None
    notif_sla_alerts: Optional[bool] = None
    notif_escalations: Optional[bool] = None
    notif_comments: Optional[bool] = None
    notif_resolutions: Optional[bool] = None
    mfa_enabled: Optional[bool] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None

    @validator("role", pre=True, always=True)
    def _normalize_role(cls, v):
        return normalize_role(v) if v is not None else v

    @validator("phone")
    def _validate_phone(cls, v):
        return validate_guinea_phone(v)

    @root_validator(pre=True)
    def _alias_unit_id(cls, values):
        if values.get("unity_id"):
            return values
        for alias in ("unit_id", "department_id", "direction_id"):
            if values.get(alias) is not None:
                try:
                    values["unity_id"] = int(values[alias])
                except (ValueError, TypeError):
                    pass
                break
        return values


class AccountResponse(BaseResponse):
    unity_id: Optional[int] = None
    unit_id: Optional[int] = None       # alias de unity_id — compatibilité frontend
    direction_id: Optional[int] = None  # réservé (pas de colonne direction séparée)
    central_user_id: Optional[int] = None
    central_user_uuid: Optional[str] = None
    name: str
    firstname: Optional[str] = None
    email: str
    phone: Optional[str] = None
    role: str
    account_status: str
    matricule: Optional[str] = None
    job: Optional[str] = None
    avatar_url: Optional[str] = None
    is_edg_employee: bool
    email_verified: bool
    mfa_enabled: bool
    availability: Optional[str] = None
    notif_sla_alerts: bool
    notif_escalations: bool
    notif_comments: bool
    notif_resolutions: bool
    activated_at: Optional[datetime] = None

    @validator("unit_id", always=True)
    def _fill_unit_id(cls, v, values):
        return v if v is not None else values.get("unity_id")

    @validator("role", pre=True, always=True)
    def _normalize_role(cls, v):
        return normalize_role(v)

    @validator("avatar_url", always=True)
    def _bust_avatar_cache(cls, v, values):
        """
        Ajoute un paramètre de version (?v=<updated_at>) à l'URL de l'avatar.
        Le nom de fichier stocké est déterministe (<account_id>.<ext>) — sans
        ce cache-buster, remplacer sa photo garde une URL identique et le
        navigateur continue d'afficher l'ancienne image depuis son cache.
        """
        if not v:
            return v
        updated_at = values.get("updated_at")
        if updated_at is None:
            return v
        return f"{v}?v={int(updated_at.timestamp())}"

    class Config:
        orm_mode = True


class ResetPasswordResponse(BaseModel):
    ok: bool = True
    default_password: str
