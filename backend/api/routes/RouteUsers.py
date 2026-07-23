from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.schemas.SchemaAccount import AccountCreate, AccountUpdate, AccountResponse

from api.schemas.base import PaginatedResponse
from api.services import AccountService
from api.core.file_validator import validate_file_magic_bytes

_AVATAR_DIR = Path(__file__).parent.parent.parent / "uploads" / "avatars"
_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
_ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024  # 2 Mo

# ── Routeur public (avatars servis sans authentification) ─────────────────────

avatars_router = APIRouter(prefix="/users", tags=["users-avatars"])

# ── Routeur profil courant (tous les utilisateurs authentifiés) ───────────────

me_router = APIRouter(
    prefix="/users",
    tags=["users-me"],
    dependencies=[Depends(get_current_user)],
)

# ── Routeur lecture annuaire (personnel — pour assignation/orientation) ──────
# Lecture seule : liste + détail. Nécessaire pour que chief/agent voient les
# collègues de leur direction (ex. dialogue "Assigner" dans la file d'attente).
# Toute mutation (create/update/role/activate/delete) reste admin uniquement,
# voir `router` ci-dessous.

staff_router = APIRouter(
    prefix="/users",
    tags=["users-staff"],
    dependencies=[Depends(require_roles("agent", "chief", "director", "admin"))],
)

# ── Routeur gestion admin des comptes (admin uniquement) ─────────────────────

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_roles("admin"))],
)


def _svc(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)


# ── Profil courant (/users/me) ────────────────────────────────────────────────

@me_router.get("/me", response_model=AccountResponse)
async def get_me(
    actor=Depends(get_current_user),
    svc: AccountService = Depends(_svc),
):
    return await svc.get_by_id(actor.id)


_SELF_UPDATE_ALLOWED = {
    "name", "firstname", "phone", "job", "matricule", "avatar_url",
    "notif_sla_alerts", "notif_escalations", "notif_comments", "notif_resolutions",
    "mfa_enabled",
}


@me_router.patch("/me", response_model=AccountResponse)
async def update_me(
    body: AccountUpdate,
    actor=Depends(get_current_user),
    svc: AccountService = Depends(_svc),
):
    # Filtrer les champs sensibles — role/direction/unit/status non modifiables par l'utilisateur
    safe = {k: v for k, v in body.dict(exclude_unset=True).items() if k in _SELF_UPDATE_ALLOWED}
    return await svc.update(actor.id, safe)


@me_router.patch("/me/availability", response_model=AccountResponse)
async def set_my_availability(
    availability: str = Query(...),
    actor=Depends(get_current_user),
    svc: AccountService = Depends(_svc),
):
    return await svc.set_availability(actor.id, availability)


@me_router.post("/me/avatar", response_model=AccountResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    actor=Depends(get_current_user),
    svc: AccountService = Depends(_svc),
):
    """Upload et met à jour l'avatar de l'utilisateur courant."""
    declared_mime = file.content_type or "application/octet-stream"
    if declared_mime not in _ALLOWED_IMAGE_MIME:
        raise HTTPException(status_code=400, detail="Format non supporté. Utilisez JPEG, PNG ou WebP.")
    data = await file.read()
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (maximum 2 Mo).")
    # C-N°1 — validation par magic bytes (empêche le spoofing de Content-Type)
    real_mime = validate_file_magic_bytes(data, declared_mime)
    ext_map = {"image/png": "png", "image/webp": "webp"}
    ext = ext_map.get(real_mime, "jpg")
    filename = f"{actor.id}.{ext}"
    _AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    (_AVATAR_DIR / filename).write_bytes(data)
    avatar_url = f"/api/v1/users/avatars/{filename}"
    return await svc.update(actor.id, {"avatar_url": avatar_url})


@me_router.delete("/me/avatar", response_model=AccountResponse)
async def delete_avatar(
    actor=Depends(get_current_user),
    svc: AccountService = Depends(_svc),
):
    """Supprime l'avatar de l'utilisateur courant."""
    if actor.avatar_url:
        filename = Path(actor.avatar_url).name
        (_AVATAR_DIR / filename).unlink(missing_ok=True)
    return await svc.update(actor.id, {"avatar_url": None})


@avatars_router.get("/avatars/{filename}")
async def get_avatar(filename: str):
    """Sert les fichiers avatar (endpoint public — pas de JWT requis)."""
    safe = Path(filename).name
    path = _AVATAR_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Avatar introuvable.")
    return FileResponse(str(path))


# ── Gestion admin des comptes (/users) ────────────────────────────────────────

@staff_router.get("/", response_model=PaginatedResponse[AccountResponse])
async def list_users(
    role: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    direction_id: Optional[int] = Query(None),
    unit_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    svc: AccountService = Depends(_svc),
):
    if search:
        return await svc.search(search, page=page, limit=limit)
    if role and unit_id:
        return await svc.list_by_role_and_unit(role, unit_id, page=page, limit=limit)
    if role and direction_id:
        return await svc.list_by_role_and_direction(role, direction_id, page=page, limit=limit)
    if unit_id:
        return await svc.list_by_unit(unit_id, page=page, limit=limit)
    if role:
        return await svc.list_by_role(role, page=page, limit=limit)
    if direction_id:
        return await svc.list_by_direction(direction_id, page=page, limit=limit)
    return await svc.list_all(page=page, limit=limit)


@staff_router.get("/{id}", response_model=AccountResponse)
async def get_user(id: int, svc: AccountService = Depends(_svc)):
    return await svc.get_by_id(id)


@router.patch("/{id}", response_model=AccountResponse)
async def update_user(
    id: int,
    body: AccountUpdate,
    svc: AccountService = Depends(_svc),
):
    return await svc.update(id, body.dict(exclude_unset=True), validate_org_assignment=True)


class RoleBody(BaseModel):
    role: str


class PasswordBody(BaseModel):
    new_password: str


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_user(body: AccountCreate, svc: AccountService = Depends(_svc)):
    return await svc.create(body.dict(), validate_org_assignment=True)


@router.patch("/{id}/role", response_model=AccountResponse)
async def set_user_role(
    id: int,
    body: RoleBody,
    svc: AccountService = Depends(_svc),
):
    return await svc.set_role(id, body.role)


@router.post("/{id}/activate", status_code=status.HTTP_200_OK)
async def activate_user(id: int, svc: AccountService = Depends(_svc)):
    await svc.get_by_id(id)  # lève 404 si l'utilisateur n'existe pas
    await svc.update(id, {"status": True, "account_status": "active"})
    return {"ok": True}


@router.post("/{id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_user(id: int, svc: AccountService = Depends(_svc)):
    await svc.get_by_id(id)  # lève 404 si l'utilisateur n'existe pas
    await svc.update(id, {"status": False, "account_status": "inactive"})
    return {"ok": True}


@router.post("/{id}/reset-password", status_code=status.HTTP_200_OK)
async def reset_user_password(id: int, body: PasswordBody, svc: AccountService = Depends(_svc)):
    await svc.set_password(id, body.new_password)
    return {"ok": True}


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(id: int, svc: AccountService = Depends(_svc)):
    await svc.delete(id)
