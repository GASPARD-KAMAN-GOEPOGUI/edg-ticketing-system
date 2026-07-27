from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.core.rbac import normalize_role
from api.schemas.SchemaAttachment import AttachmentCreate, AttachmentUpdate, AttachmentResponse
from api.schemas.base import PaginatedResponse
from api.services import AttachmentService, RequestService

router = APIRouter(
    prefix="/attachments",
    tags=["attachments"],
    dependencies=[Depends(get_current_user)],
)


def _svc(db: AsyncSession = Depends(get_db)) -> AttachmentService:
    return AttachmentService(db)


def _req_svc(db: AsyncSession = Depends(get_db)) -> RequestService:
    return RequestService(db)


def _check_attachment_access(actor, req) -> None:
    """Même politique d'accès que dans RouteRequest._check_request_access."""
    role = normalize_role(actor.role)
    if role == "admin":
        return
    if role == "user":
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")
        return
    if role in {"agent-support", "chief-service", "chief-departement"}:
        if actor.unit_id and req.unit_id and str(req.unit_id) == str(actor.unit_id):
            return
        if actor.direction_id and req.direction_id and str(req.direction_id) == str(actor.direction_id):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hors périmètre.")
    if role == "director":
        if actor.direction_id and req.direction_id and str(req.direction_id) == str(actor.direction_id):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Hors périmètre.")


@router.get("/by-request/{request_id}", response_model=PaginatedResponse)
async def list_by_request(
    request_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    """C-N°4 — ownership check avant de lister les pièces jointes d'une demande."""
    req = await req_svc.get_by_id(request_id)
    _check_attachment_access(actor, req)
    return await svc.list_by_request(request_id, page=page, limit=limit)


@router.get("/pending-scan", response_model=PaginatedResponse)
async def list_pending_scan(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _=Depends(require_roles("admin")),
    svc: AttachmentService = Depends(_svc),
):
    return await svc.list_pending_scan(page=page, limit=limit)


@router.get("/quarantined", response_model=PaginatedResponse)
async def list_quarantined(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _=Depends(require_roles("admin")),
    svc: AttachmentService = Depends(_svc),
):
    return await svc.list_quarantined(page=page, limit=limit)


@router.get("/{id}", response_model=AttachmentResponse)
async def get_attachment(
    id: str,
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_svc),
    req_svc: RequestService = Depends(_req_svc),
):
    """C-N°4 — ownership check avant de retourner les métadonnées d'une pièce jointe."""
    att = await svc.get_by_id(id)
    req = await req_svc.get_by_id(str(att.request_id))
    _check_attachment_access(actor, req)
    return att


@router.post(
    "/",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("admin"))],
    summary="Admin uniquement — enregistrement direct d'une pièce jointe (usage interne)",
)
async def create_attachment(
    body: AttachmentCreate,
    svc: AttachmentService = Depends(_svc),
):
    """
    C-03 — Restreint admin-only.
    Les uploads utilisateur passent exclusivement par POST /requests/{id}/attachments
    (multipart/form-data avec validation MIME, taille et storage_path généré côté serveur).
    """
    return await svc.create(body.dict())


@router.patch("/{id}/scan-result", response_model=AttachmentResponse)
async def update_scan_result(
    id: str,
    clamav_clean: bool = Query(..., description="True = fichier sain, False = menace détectée"),
    scan_status: str = Query(..., description="clean | quarantined | error"),
    _=Depends(require_roles("admin")),
    svc: AttachmentService = Depends(_svc),
):
    """H-04 — signature corrigée : clamav_clean + scan_status (aligné avec le repository)."""
    return await svc.update_scan_result(id, clamav_clean=clamav_clean, scan_status=scan_status)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    id: str,
    _=Depends(require_roles("admin")),
    svc: AttachmentService = Depends(_svc),
):
    await svc.delete(id)
