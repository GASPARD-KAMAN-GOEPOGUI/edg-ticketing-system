from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.models.ModelAccount import Account
from api.schemas.SchemaRequest import RequestCreate, RequestWorkflowCreate, RequestUpdate, RequestResponse, RequestListItemResponse, RequestSearch
from api.schemas.SchemaWorkflowDetail import WorkflowDetailResponse
from api.schemas.SchemaEscalation import EscalationResponse
from api.schemas.SchemaAttachment import AttachmentResponse
from pydantic import BaseModel
from api.schemas.base import PaginatedResponse
from api.services import RequestService, AttachmentService, RequestExportService
from api.services.ServiceExport import build_response
from api.repositories import WorkflowDetailRepository, WorkflowRepository
from api.services.ServiceClamAV import scan_bytes as clamav_scan
from api.core.ticket_actions import (
    assert_escalation_allowed,
    assert_exceptional_escalation_reason,
    assert_requester_is_not_handler,
    assert_ticket_action,
)
from api.core.file_validator import validate_file_magic_bytes
from api.core.rbac import normalize_role
from api import storage
from api.dependencies import get_current_user

router = APIRouter(
    prefix="/requests",
    tags=["requests"],
    dependencies=[Depends(get_current_user)],
)

public_router = APIRouter(prefix="/requests", tags=["requests-public"])

_ALLOWED_MIME = {
    "image/jpeg", "image/png", "image/webp", "application/pdf",
}
_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 Mo
_MAX_FILES_PER_REQUEST = 5


async def _get_dir_unity_ids(db: AsyncSession, dir_unity_id: int) -> set[int]:
    """Retourne le set {direction + tous ses services} depuis l'organigramme (2 niveaux)."""
    from sqlalchemy import select as sa_select
    from api.models.ModelOrganigram import Organigram
    from api.models.ModelUnity import Unity

    r1 = await db.execute(
        sa_select(Organigram.id)
        .where(Organigram.unity_id == dir_unity_id, Organigram.deleted_at.is_(None))
        .limit(1)
    )
    org_id = r1.scalar_one_or_none()
    ids: set[int] = {dir_unity_id}
    if org_id:
        r2 = await db.execute(
            sa_select(Organigram.unity_id)
            .where(Organigram.parent_id == org_id, Organigram.deleted_at.is_(None))
        )
        ids.update(uid for (uid,) in r2.all())
    r3 = await db.execute(
        sa_select(Unity.id)
        .where(Unity.parent_direction_id == dir_unity_id, Unity.deleted_at.is_(None))
    )
    ids.update(uid for (uid,) in r3.all())
    return ids


def _check_request_access(actor, req, allowed_dir_unity_ids: set[int] | None = None) -> None:
    """
    Vérifie que l'acteur a le droit d'accéder à la demande `req`.
    Lève HTTP 403 si l'acteur est hors périmètre.

    Politique d'accès :
      tout rôle        → ses propres demandes en lecture personnelle
      tout rôle        → les demandes qui lui sont personnellement assignées (assignee_id),
                         même hors de son unité courante (BR-ROLE-AGENT-001, routage direct)
      user             → uniquement ses propres demandes
      agent-support/chief-service → demandes de leur unité (service) uniquement
      chief-departement → demandes de leur département ET tous ses services (allowed_dir_unity_ids)
      director         → demandes de leur direction ET tous ses services (allowed_dir_unity_ids)
      admin            → accès global
    """
    actor_id = getattr(actor, "id", None)
    requester_id = getattr(req, "requester_id", None)
    if actor_id is not None and requester_id is not None and str(requester_id) == str(actor_id):
        return

    assignee_id = getattr(req, "assignee_id", None)
    if actor_id is not None and assignee_id is not None and str(assignee_id) == str(actor_id):
        return

    role = normalize_role(actor.role)
    if role == "admin":
        return

    if role == "user":
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé : vous ne pouvez accéder qu'à vos propres demandes.",
            )
        return

    if role in {"agent-support", "chief-service", "chief-departement"}:
        allowed_ids = set(allowed_dir_unity_ids or set())
        if actor.unity_id is not None:
            allowed_ids.add(int(actor.unity_id))
        request_ids = {int(req.unity_id)} if req.unity_id is not None else set()
        if allowed_ids and request_ids.intersection(allowed_ids):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : cette demande n'est pas dans votre périmètre.",
        )

    if role == "director":
        if actor.unity_id and req.unity_id:
            ids = allowed_dir_unity_ids if allowed_dir_unity_ids else {actor.unity_id}
            if req.unity_id in ids:
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : cette demande n'est pas dans votre direction.",
        )


async def _resolve_access(actor, req, db: AsyncSession) -> None:
    """Wrapper async : pré-calcule les unity_ids autorisés puis vérifie l'accès."""
    dir_ids = None
    # Seuls chief-departement (departement + services rattaches) et director
    # (direction + services rattaches) beneficient d'un perimetre elargi ;
    # agent-support/chief-service restent bornes a leur propre unite.
    if normalize_role(actor.role) in {"chief-departement", "director"} and actor.unity_id:
        dir_ids = await _get_dir_unity_ids(db, actor.unity_id)
    _check_request_access(actor, req, dir_ids)


async def _check_unity_access(actor, unity_id: str, db: AsyncSession) -> None:
    role = normalize_role(actor.role)
    if role == "admin":
        return

    try:
        requested_unity_id = int(unity_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identifiant d'unité invalide.",
        )

    if role in {"agent-support", "chief-service"}:
        if actor.unity_id and int(actor.unity_id) == requested_unity_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : cette unité n'est pas dans votre périmètre.",
        )

    if role in {"chief-departement", "director"}:
        if actor.unity_id:
            allowed_ids = await _get_dir_unity_ids(db, int(actor.unity_id))
            if requested_unity_id in allowed_ids:
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : cette unité n'est pas dans votre direction.",
        )

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")


def _svc(db: AsyncSession = Depends(get_db)) -> RequestService:
    return RequestService(db)


def _detail_repo(db: AsyncSession = Depends(get_db)) -> WorkflowDetailRepository:
    return WorkflowDetailRepository(db)


def _wf_repo(db: AsyncSession = Depends(get_db)) -> WorkflowRepository:
    return WorkflowRepository(db)


async def _timeline_workflow(wf_repo: WorkflowRepository, request_id: str):
    wf = await wf_repo.find_active_workflow(request_id)
    if wf is not None:
        return wf
    workflows = await wf_repo.find_by_request(request_id)
    return workflows[0] if workflows else None


def _att_svc(db: AsyncSession = Depends(get_db)) -> AttachmentService:
    return AttachmentService(db)


def _export_svc(db: AsyncSession = Depends(get_db)) -> RequestExportService:
    return RequestExportService(db)


def _actor_display_name(actor) -> str | None:
    parts = [getattr(actor, "firstname", None), getattr(actor, "name", None)]
    return " ".join(part for part in parts if part) or None


async def _validate_attachment_ids(
    att_svc: AttachmentService, request_id: str, attachment_ids: Optional[list[str]]
) -> list[dict]:
    """BR-TRANSMIT-001 — mêmes garanties que les pièces jointes de commentaire
    (BR-ATTACHMENT-001) : chaque pièce jointe fournie doit déjà avoir été uploadée
    sur cette même demande."""
    if not attachment_ids:
        return []
    validated: list[dict] = []
    for att_id in attachment_ids:
        att = await att_svc.get_by_id(att_id)
        if str(att.request_id) != str(request_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Une pièce jointe fournie n'appartient pas à cette demande.",
            )
        validated.append({
            "attachment_id": str(att.id),
            "filename": att.filename,
            "mime_type": att.mime_type,
            "size_bytes": att.size_bytes,
        })
    return validated


def _resolve_comment_peer(event, req) -> Optional[str]:
    """
    BR-MESSAGING-PAIR-001 — résout la clé de conversation (`peer_id`) d'un
    événement `comment_added` : toujours le côté "intervenant" de la paire
    {demandeur, peer}, jamais le demandeur lui-même et jamais inversé selon
    qui a écrit — un message du demandeur et la réponse de l'intervenant
    portent le même `peer_id`, pour rester dans le même fil.

    Priorité à `infos.peer_id`, écrit explicitement à la création depuis cette
    évolution. Fallback pour les événements historiques (créés avant
    l'introduction de `peer_id`, jamais migrés en base) :
      - directive (`infos.is_directive`) -> `infos.target_user_id` (déjà résolu,
        inchangé) ;
      - auteur = demandeur -> assigné courant du ticket au moment de la lecture
        (meilleure estimation : le front n'envoyait jusqu'ici que des messages
        destinés à l'intervenant en charge) ;
      - auteur = staff -> lui-même (chaque intervenant historique garde son
        propre fil avec le demandeur, jamais mélangé avec celui d'un autre).
    """
    infos = event.infos if isinstance(event.infos, dict) else {}
    peer_id = infos.get("peer_id")
    if peer_id:
        return str(peer_id)
    if infos.get("is_directive"):
        target = infos.get("target_user_id")
        return str(target) if target else None
    author_id = infos.get("actor_id") or (str(event.agent_id) if getattr(event, "agent_id", None) else None)
    requester_id = getattr(req, "requester_id", None)
    if author_id and requester_id and str(author_id) == str(requester_id):
        assignee_id = getattr(req, "assignee_id", None)
        return str(assignee_id) if assignee_id else None
    return str(author_id) if author_id else None


def _visible_comment_responses(
    events: list[WorkflowDetailResponse], req, actor, *, public_only: bool = False
) -> list[WorkflowDetailResponse]:
    """
    BR-MESSAGING-PAIR-001 — filtre les événements `comment_added` pour ne
    garder que les conversations dont `actor` fait réellement partie. Le
    Journal d'audit (tout événement non `comment_added`) n'est jamais touché
    ici, sa visibilité reste régie par le RBAC ticket standard (`_resolve_access`).

      - admin -> supervision : tout est visible (lecture seule côté frontend) ;
      - demandeur (ou `public_only`, cf. suivi public par ref+email/téléphone,
        qui agit pour son propre compte) -> toute conversation normale, puisque
        chacune l'inclut par construction (BR-MESSAGING-PAIR-001 §1) ; les
        directives chef->agent restent masquées (jamais destinées au demandeur) ;
      - staff non-admin -> uniquement sa propre conversation avec le demandeur
        (peer résolu == lui, ou il en est l'auteur) ; pour une directive,
        uniquement s'il en est l'auteur (chef) ou la cible (agent).
    """
    role = normalize_role(getattr(actor, "role", None)) if actor is not None else None
    viewer_id = getattr(actor, "id", None)
    requester_id = getattr(req, "requester_id", None)
    is_owner = (
        public_only
        or role == "user"
        or (viewer_id is not None and requester_id is not None and str(requester_id) == str(viewer_id))
    )
    visible: list[WorkflowDetailResponse] = []
    for event in events:
        if event.event_type != "comment_added":
            visible.append(event)
            continue
        infos = event.infos if isinstance(event.infos, dict) else {}
        is_directive = bool(infos.get("is_directive"))
        peer_id = _resolve_comment_peer(event, req)
        enriched = event.copy(update={"infos": {**infos, "peer_id": peer_id}}) if peer_id else event

        if role == "admin":
            visible.append(enriched)
            continue
        if is_owner:
            if not is_directive:
                visible.append(enriched)
            continue
        if viewer_id is None:
            continue
        author_id = infos.get("actor_id") or (str(event.agent_id) if event.agent_id else None)
        if is_directive:
            target = infos.get("target_user_id")
            if (author_id and str(author_id) == str(viewer_id)) or (target and str(target) == str(viewer_id)):
                visible.append(enriched)
            continue
        if (peer_id and str(peer_id) == str(viewer_id)) or (author_id and str(author_id) == str(viewer_id)):
            visible.append(enriched)
    return visible


async def _attach_participant_avatars(schema: RequestResponse, svc: RequestService) -> RequestResponse:
    """
    Résout par lot les avatars des intervenants d'un ticket (demandeur, assigné,
    acteurs/destinataires du journal). Les acteurs du journal (`infos.actor_id`,
    `infos.target_user_id`) ne sont référencés que par id dans un champ JSON —
    pas de relation SQLAlchemy directe permettant un join — d'où une résolution
    en une seule requête groupée ici plutôt qu'un champ calculé sur le modèle.
    """
    ids: set[int] = set()
    if schema.requester_id:
        ids.add(schema.requester_id)
    if schema.assignee_id:
        ids.add(schema.assignee_id)
    for event in schema.timelines or []:
        infos = event.infos if isinstance(event.infos, dict) else {}
        for key in ("actor_id", "target_user_id", "to_user_id"):
            raw_id = infos.get(key)
            if raw_id is None:
                continue
            try:
                ids.add(int(raw_id))
            except (TypeError, ValueError):
                continue
    if not ids:
        return schema

    result = await svc.session.execute(
        select(Account.id, Account.avatar_url, Account.updated_at).where(Account.id.in_(ids))
    )
    avatars: dict[str, str] = {}
    for account_id, avatar_url, updated_at in result.all():
        if not avatar_url:
            continue
        version = int(updated_at.timestamp()) if updated_at else 0
        avatars[str(account_id)] = f"{avatar_url}?v={version}"
    if not avatars:
        return schema
    return schema.copy(update={"participant_avatars": avatars})


async def _request_response_for_actor(req, svc: RequestService, actor=None, *, public_only: bool = False) -> RequestResponse:
    schema = svc._decrypt_schema(RequestResponse.from_orm(req))
    schema = schema.copy(update={
        "timelines": _visible_comment_responses(schema.timelines, req, actor, public_only=public_only),
    })
    return await _attach_participant_avatars(schema, svc)


# ── Listes ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedResponse[RequestListItemResponse])
async def list_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=1000),
    request_status: Optional[str] = Query(None),
    exclude_status: Optional[str] = Query(None),
    is_external: Optional[bool] = Query(None),
    direction_id: Optional[str] = Query(None),
    unit_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    requester_id: Optional[str] = Query(None),
    sla_breached: Optional[bool] = Query(None),
    in_triage: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, min_length=1),
    date_from: Optional[str] = Query(None, description="Date de début ISO (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Date de fin ISO (YYYY-MM-DD)"),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Liste filtrée et paginée — visibilité restreinte au périmètre de l'utilisateur."""
    # Vue personnelle : l'acteur demande SES propres demandes en tant que requester,
    # ou SES propres tickets assignés (BR-ROLE-AGENT-001 — « Mes tickets » filtre
    # uniquement par assignee_id, sans restriction d'unité : un ticket peut avoir
    # été assigné directement à l'agent hors de son unité courante, notamment via
    # le routage dynamique qui permet de cibler un agent sans passer par chef/direction).
    # Dans ces deux cas, on bypasse le forcing unit_id/direction_id pour tous les rôles.
    is_own_view = requester_id is not None and requester_id == str(actor.id)
    is_own_assignee_view = assignee_id is not None and assignee_id == str(actor.id)

    # Filtrage RBAC — forcé, le client ne peut pas étendre son périmètre (C-N°3)
    actor_role = normalize_role(actor.role)
    if is_own_view or is_own_assignee_view:
        pass  # requester_id/assignee_id = actor.id suffit ; unit/direction non forcés
    elif actor_role == "user":
        requester_id = str(actor.id)           # toujours ses propres demandes
    elif actor_role in {"agent-support", "chief-service"}:
        if actor.unity_id:
            unit_id = str(actor.unity_id)       # forcé, ignore le paramètre client
            direction_id = None
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une unité. Contactez un administrateur.",
            )
    elif actor_role == "chief-departement":
        if actor.unity_id:
            direction_id = str(actor.unity_id)  # forcé : departement + services rattaches
            unit_id = None
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une unité. Contactez un administrateur.",
            )
    elif actor_role == "director":
        if actor.unity_id:
            direction_id = str(actor.unity_id)  # forcé
            unit_id = None
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une direction. Contactez un administrateur.",
            )
    # admin : visibilité globale — filtres client acceptés

    has_filter = any(v is not None for v in [
        request_status, exclude_status, is_external, direction_id, unit_id,
        assignee_id, requester_id, sla_breached, in_triage, search,
        date_from, date_to,
    ])
    if has_filter:
        return await svc.list_filtered(
            request_status=request_status,
            exclude_status=exclude_status,
            is_external=is_external,
            direction_id=direction_id,
            unit_id=unit_id,
            assignee_id=assignee_id,
            requester_id=requester_id,
            # BR-REQUESTER-NO-SELF-TREATMENT-001 — defense en profondeur : "Ma boite
            # de traitement" (assignee_id == soi-meme) n'affiche jamais un ticket dont
            # l'acteur est aussi le demandeur, meme en cas d'anomalie amont.
            exclude_requester_id=str(actor.id) if is_own_assignee_view else None,
            sla_breached=sla_breached,
            in_triage=in_triage,
            search=search,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
    return await svc.list_all(page=page, limit=limit)


_staff = Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin"))


@router.get("/triage", response_model=PaginatedResponse[RequestListItemResponse])
async def list_triage(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_pending_triage(page=page, limit=limit)


@router.get("/sla-breached", response_model=PaginatedResponse[RequestListItemResponse])
async def list_sla_breached(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_sla_breached(page=page, limit=limit)


@router.get("/transmitted", response_model=PaginatedResponse[RequestListItemResponse])
async def list_transmitted_by_me(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=1),
    retransmitted_only: bool = Query(False, description="BR-RETRANSMIT-001 — ne garder que les tickets transmis au moins 2 fois par l'acteur"),
    actor=_staff,
    svc: RequestService = Depends(_svc),
):
    """BR-TRANSMIT-001 — tickets que l'acteur courant a personnellement transmis
    à un moment de leur historique ET dont il n'est plus l'intervenant actuel
    (assignee_id != acteur). Si le ticket lui revient depuis, il quitte cette
    vue et réapparaît dans "Ma boîte de traitement" — l'historique de
    transmission reste intact, seule la vue opérationnelle change.
    Lecture seule, scope = ses propres actions passées ; ne touche à aucune
    règle de qualification/assignation/transmission."""
    return await svc.list_transmitted_by_me(
        str(actor.id), search=search, page=page, limit=limit, retransmitted_only=retransmitted_only,
    )


@router.get("/stats/by-status")
async def stats_by_status(_=_staff, svc: RequestService = Depends(_svc)):
    return await svc.count_by_status()


_workload_staff = Depends(require_roles("chief-service", "chief-departement", "admin"))


@router.get("/workload-by-unit")
async def workload_by_unit(
    unit_id: Optional[str] = Query(None, description="Admin uniquement — ignoré pour chief-service/chief-departement"),
    direction_id: Optional[str] = Query(None, description="Admin uniquement — expanse departement+services"),
    actor=Depends(get_current_user),
    _staff_guard=_workload_staff,
    db: AsyncSession = Depends(get_db),
    svc: RequestService = Depends(_svc),
):
    """Charge actuelle (tickets non terminaux) par agent assigné — Centre de répartition (Lot 2/3)."""
    actor_role = normalize_role(actor.role)
    if actor_role == "chief-service":
        if not actor.unity_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une unité. Contactez un administrateur.",
            )
        unity_ids = {int(actor.unity_id)}
    elif actor_role == "chief-departement":
        if not actor.unity_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une unité. Contactez un administrateur.",
            )
        unity_ids = await _get_dir_unity_ids(db, int(actor.unity_id))
    else:  # admin — filtres client acceptés
        if unit_id:
            unity_ids = {int(unit_id)}
        elif direction_id:
            unity_ids = await _get_dir_unity_ids(db, int(direction_id))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unit_id ou direction_id requis pour le rôle admin.",
            )
    return await svc.workload_by_unit(list(unity_ids))


@router.get("/search", response_model=PaginatedResponse[RequestListItemResponse])
async def search_requests(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    # Les utilisateurs standard ne recherchent que dans leurs propres demandes
    if normalize_role(actor.role) == "user":
        return await svc.list_filtered(requester_id=str(actor.id), search=q, page=page, limit=limit)
    return await svc.search(q, page=page, limit=limit)


@public_router.get("/track", response_model=RequestResponse)
async def track_request(
    ref: str = Query(..., description="Référence EDG-XXXX-XXXX"),
    email: Optional[str] = Query(None, description="Email associé au compte demandeur"),
    phone: Optional[str] = Query(None, description="Téléphone associé au compte demandeur"),
    svc: RequestService = Depends(_svc),
):
    """Suivi public — nécessite ref + (email ou téléphone) du compte ayant créé la demande."""
    req = await svc.track(ref.strip().upper(), email=email, phone=phone)
    return await _request_response_for_actor(req, svc, public_only=True)


@router.get("/queue", response_model=PaginatedResponse[RequestListItemResponse])
async def list_queue(
    page: int = Query(1, ge=1),
    # le=200 (pas 100) : "Mes tickets" et la boîte de traitement du chef appellent
    # cet endpoint avec limit=200 pour afficher une vue complète sans pagination.
    limit: int = Query(20, ge=1, le=200),
    direction_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None),
    unassigned_only: bool = Query(False),
    priority: Optional[str] = Query(None),
    request_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, min_length=1),
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """File d'attente active — réservée aux agents et supérieurs, filtrée par périmètre."""
    # Forçage RBAC — le paramètre client direction_id est ignoré (C-N°3)
    actor_role = normalize_role(actor.role)
    if actor_role in {"agent-support", "chief-service", "chief-departement", "director"}:
        direction_id = str(actor.unity_id) if actor.unity_id else None
    return await svc.list_queue(
        direction_id=direction_id,
        assignee_id=assignee_id,
        unassigned_only=unassigned_only,
        priority=priority,
        request_status=request_status,
        search=search,
        page=page,
        limit=limit,
    )


class QualifyTriageBody(BaseModel):
    category: str
    priority: str
    direction_id: Optional[str] = None
    unit_id: Optional[str] = None
    assignee_id: Optional[str] = None


@router.post("/{id}/qualify", response_model=RequestResponse)
async def qualify_triage(
    id: str,
    body: QualifyTriageBody,
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Qualifie une demande de triage — reserve aux roles operationnels."""
    return await svc.qualify_triage(
        id,
        body.dict(exclude_none=True),
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
    )


@router.get("/by-status/{request_status}", response_model=PaginatedResponse[RequestListItemResponse])
async def list_by_status(
    request_status: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_by_status(request_status, page=page, limit=limit)


@router.get("/by-assignee/{assignee_id}", response_model=PaginatedResponse[RequestListItemResponse])
async def list_by_assignee(
    assignee_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=_staff,
    svc: RequestService = Depends(_svc),
):
    return await svc.list_by_assignee(assignee_id, page=page, limit=limit)


@router.get("/by-requester/{requester_id}", response_model=PaginatedResponse[RequestListItemResponse])
async def list_by_requester(
    requester_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    if actor.role == "user" and str(actor.id) != requester_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé aux demandes d'un autre utilisateur.",
        )
    return await svc.list_by_requester(requester_id, page=page, limit=limit)


@router.get("/by-direction/{direction_id}", response_model=PaginatedResponse[RequestListItemResponse])
async def list_by_direction(
    direction_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    await _check_unity_access(actor, direction_id, db)
    return await svc.list_by_direction(direction_id, page=page, limit=limit)


@router.get("/by-unity/{unity_id}", response_model=PaginatedResponse[RequestListItemResponse])
async def list_by_unity(
    unity_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """Requêtes d'une unité spécifique."""
    await _check_unity_access(actor, unity_id, db)
    return await svc.list_by_unity(unity_id, page=page, limit=limit)


@router.get("/ref/{ref}", response_model=RequestResponse)
async def get_by_ref(
    ref: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """H-07 — ownership check : un user ne voit que ses propres demandes."""
    req = await svc.get_by_ref(ref)
    await _resolve_access(actor, req, db)
    return await _request_response_for_actor(req, svc, actor)


@router.get("/{id}", response_model=RequestResponse)
async def get_request(
    id: str,
    include_deleted: bool = Query(False, description="Admin uniquement : inclut les tickets archivés/supprimés."),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """H-07 — ownership check : un user ne voit que ses propres demandes."""
    req = await svc.get_by_id(id, include_deleted=include_deleted and actor.role == "admin")
    await _resolve_access(actor, req, db)
    return await _request_response_for_actor(req, svc, actor)


@router.get("/{id}/export")
async def export_request_dossier(
    id: str,
    format: str = Query("excel", pattern="^(excel|pdf)$"),
    _actor=Depends(require_roles("admin")),
    export_svc: RequestExportService = Depends(_export_svc),
):
    """Dossier fonctionnel complet d'une demande — Administration uniquement.
    Lecture seule : aucun changement de statut, aucune notification, aucun
    événement métier. Aucune donnée SLA/délai n'est incluse."""
    content, filename = await export_svc.build_dossier(id, fmt=format)
    return build_response(content, format, filename)


# ── Premier résultat filtré (pattern edgrh GET /items/) ───────────────────────

@router.get(
    "/items/",
    response_model=RequestResponse,
    summary="Premier résultat filtré — pattern edgrh get_items()",
    description=(
        "Retourne LA PREMIÈRE demande correspondant aux critères. "
        "Utilisez GET / pour une liste paginée, GET /search pour la recherche textuelle."
    ),
)
async def get_request_item(
    params: RequestSearch = Depends(),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    return await svc.get_first_filtered(
        request_status=params.request_status,
        unity_id=str(params.unity_id) if params.unity_id else None,
        assignee_id=str(params.assignee_id) if params.assignee_id else None,
        requester_id=str(params.requester_id) if params.requester_id else None,
        is_external=params.is_external,
        in_triage=params.in_triage,
        sla_breached=params.sla_breached,
        priority=params.priority,
    )


# ── Créations ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    body: RequestWorkflowCreate,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """C-02 — requester_id forcé depuis le JWT.
    Supporte workflows:[] pour créer le circuit de validation en même temps que la demande
    (pattern edgrh POST /demand/workflow avec DemandWorkflowCreateSchema)."""
    data = body.dict()
    data["requester_id"] = actor.id
    data["requester_role"] = str(actor.role)
    obj = await svc.create(data)
    return svc._decrypt_schema(RequestResponse.from_orm(obj))


# ── Modifications ─────────────────────────────────────────────────────────────

_STAFF_UPDATE_FIELDS = {"request_status", "status_reason"}


@router.put("/{id}", response_model=RequestResponse)
async def update_request(
    id: str,
    body: RequestUpdate,
    actor=Depends(require_roles("user", "agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    data = body.dict(exclude_unset=True)
    req = await svc.get_by_id(id)
    # Verification de perimetre — absente jusqu'ici sur cette route generique (correctif
    # securite Lot 2.1) : un acteur staff ne pouvait modifier n'importe quel champ d'un
    # ticket hors de son unite/direction, la seule garde etant require_roles. `_resolve_access`
    # bypasse deja demandeur/assignee/admin (voir `_check_request_access`).
    await _resolve_access(actor, req, db)
    if str(req.requester_id) == str(actor.id):
        # Quand l'acteur est le demandeur, il garde uniquement les droits demandeur.
        # Les actions metier sensibles passent par leurs routes dediees.
        allowed = {"title", "description"}
        data = {k: v for k, v in data.items() if k in allowed}
    elif actor.role == "user":
        # Un utilisateur ne peut modifier que ses propres demandes (titre + description)
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(status_code=403, detail="Vous ne pouvez modifier que vos propres demandes.")
        allowed = {"title", "description"}
        data = {k: v for k, v in data.items() if k in allowed}
    elif actor.role != "admin":
        # Staff non-admin : seule la transition de statut (in_progress/pending — take_ownership,
        # resume, request_info) passe par cette route generique. Tout le reste (categorie,
        # priorite, assignee_id, unity_id, sla_*...) a sa route dediee (qualify/assign/priority/
        # reassign) avec ses propres garde-fous — pas de bypass via PATCH generique.
        data = {k: v for k, v in data.items() if k in _STAFF_UPDATE_FIELDS}
    if data.get("assignee_id") is not None:
        # BR-REQUESTER-NO-SELF-TREATMENT-001 — seul chemin restant ou assignee_id
        # est PATCHable ici (admin, cf. commentaire ci-dessus) ; aucune route dediee
        # (assign/qualify/transmit/reassign) ne passe par ce PATCH generique.
        assert_requester_is_not_handler(req, data["assignee_id"])
    return await svc.update(
        id,
        data,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
    )


class RequesterEditBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

    class Config:
        extra = "forbid"


@router.put("/{id}/requester-edit", response_model=RequestResponse)
async def requester_edit(
    id: str,
    body: RequesterEditBody,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Modification personnelle par le demandeur — uniquement titre/description si status in (new, qualifying).
    Ouvert à tous les rôles : le service valide que l'acteur est bien le demandeur du ticket (C-02)."""
    return await svc.requester_edit(
        id,
        body.dict(exclude_none=True),
        actor_id=str(actor.id),
        actor_role=str(actor.role),
    )


@router.post("/{id}/assign", response_model=RequestResponse)
async def assign_request(
    id: str,
    assignee_id: str = Query(...),
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Assignation d'une demande — roles operationnels, perimetre controle par le service."""
    return await svc.assign(
        id,
        assignee_id,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
    )


class ResolveBody(BaseModel):
    summary: str
    solution: str
    work_done: str
    recommendations: Optional[str] = None
    attachment_ids: Optional[list[str]] = None


@router.post("/{id}/resolve", response_model=RequestResponse)
async def resolve_request(
    id: str,
    body: ResolveBody,
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
    att_svc: AttachmentService = Depends(_att_svc),
):
    """BR-TRANSMIT-001 — "Terminer le traitement". Autorisé à l'intervenant actuel
    (request.assignee_id == actor.id) parmi les rôles traitants : agent-support,
    chief-service, chief-departement (rouvert — remplace Lot 3.2), director (n'est
    plus limité aux tickets escaladés — remplace BR-DIRECTOR-RESOLVE-001). Résumé,
    solution et travail réalisé désormais obligatoires pour tous les rôles."""
    attachments = await _validate_attachment_ids(att_svc, id, body.attachment_ids)
    return await svc.resolve(
        id,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
        summary=body.summary,
        solution=body.solution,
        work_done=body.work_done,
        recommendations=body.recommendations,
        attachments=attachments,
    )


class TransmitTreatmentBody(BaseModel):
    to_user_id: str
    work_done: str
    reason: str
    instruction: Optional[str] = None
    attachment_ids: Optional[list[str]] = None


@router.post("/{id}/transmit", response_model=RequestResponse)
async def transmit_treatment_request(
    id: str,
    body: TransmitTreatmentBody,
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
    att_svc: AttachmentService = Depends(_att_svc),
):
    """BR-TRANSMIT-001 — "Transmettre le traitement". Autorisé uniquement à
    l'intervenant actuel (request.assignee_id == actor.id) parmi les rôles traitants.
    La cible peut être choisie librement dans toute l'organisation (aucune restriction
    de direction/service) sous réserve d'être active et de porter un rôle traitant —
    vérifié côté backend, pas seulement masqué côté frontend."""
    attachments = await _validate_attachment_ids(att_svc, id, body.attachment_ids)
    return await svc.transmit_treatment(
        id,
        to_user_id=body.to_user_id,
        work_done=body.work_done,
        reason=body.reason,
        instruction=body.instruction,
        attachments=attachments,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
    )


@router.post("/{id}/close", response_model=RequestResponse)
async def close_request(
    id: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Cloture — demandeur (ses propres tickets resolus) ou agent-support/chief-service/chief-departement/directeur/admin."""
    if actor.role == "user":
        req = await svc.get_by_id(id)
        if str(req.requester_id) != str(actor.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez clôturer que vos propres demandes.",
            )
        if req.request_status not in ("resolved",):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vous pouvez clôturer uniquement une demande à l'état 'resolved'.",
            )
    elif normalize_role(actor.role) not in {"agent-support", "chief-service", "chief-departement", "director", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")
    return await svc.close(
        id,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
    )


class ReopenBody(BaseModel):
    reason: str
    actor_name: Optional[str] = None


@router.post("/{id}/reopen", response_model=RequestResponse)
async def reopen_request(
    id: str,
    body: ReopenBody,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """
    BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : réservé au demandeur
    propriétaire du ticket, motif obligatoire, aucune approbation hiérarchique.
    Remplace l'ancien mécanisme en deux phases (`/request-reopen` puis approbation
    chef/directeur/admin via `/reopen`) — un seul comportement métier officiel.
    """
    req = await svc.get_by_id(id)
    if req.requester_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez réouvrir que vos propres tickets.",
        )
    return await svc.reopen(
        id,
        actor_id=str(actor.id),
        actor_name=body.actor_name or _actor_display_name(actor) or actor.name,
        actor_role=actor.role,
        actor=actor,
        reason=body.reason,
    )


@router.post("/{id}/cancel", response_model=RequestResponse)
async def cancel_request(
    id: str,
    reason: Optional[str] = Query(None),
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
):
    """Annulation — demandeur (ses propres tickets) ou agent-support/chief-service/chief-departement/admin."""
    if actor.role == "user":
        req = await svc.get_by_id(id)
        if req.requester_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez annuler que vos propres demandes.",
            )
    elif normalize_role(actor.role) not in {"agent-support", "chief-service", "chief-departement", "director", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès refusé.")
    return await svc.cancel(
        id,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
        reason=reason,
    )


class RejectBody(BaseModel):
    reason: str


@router.post("/{id}/reject", response_model=RequestResponse)
async def reject_request(
    id: str,
    body: RejectBody,
    actor=Depends(require_roles("chief-service", "chief-departement", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Rejet d'un ticket par le chef de service — motif obligatoire."""
    return await svc.reject(
        id,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
        reason=body.reason,
    )


class PriorityBody(BaseModel):
    priority: str


@router.post("/{id}/priority", response_model=RequestResponse)
async def change_request_priority(
    id: str,
    body: PriorityBody,
    actor=Depends(require_roles("chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Changement de priorité — autorisé à tous les chefs dans leur périmètre."""
    return await svc.change_priority(
        id,
        body.priority,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
    )


class ReassignBody(BaseModel):
    target_unity_id: str
    reason: Optional[str] = None


@router.post("/{id}/reassign", response_model=RequestResponse)
async def reassign_request(
    id: str,
    body: ReassignBody,
    actor=Depends(require_roles("chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Réaffectation d'un ticket à un autre service — chief-departement, director, admin
    (Lot 2.5 : chief-service n'a plus accès à cette action, cf. ticket_actions.py)."""
    return await svc.reassign_service(
        id,
        body.target_unity_id,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
        reason=body.reason,
    )


class TransferDirectionBody(BaseModel):
    target_direction_id: str
    reason: str


@router.post("/{id}/transfer-direction", response_model=RequestResponse)
async def transfer_direction_request(
    id: str,
    body: TransferDirectionBody,
    actor=Depends(require_roles("director", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Transfert inter-direction — réservé au directeur source et à l'admin."""
    return await svc.transfer_direction(
        id,
        body.target_direction_id,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
        actor=actor,
        reason=body.reason,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_request(
    id: str,
    _=Depends(require_roles("admin")),
    svc: RequestService = Depends(_svc),
):
    await svc.delete(id)


# ── Escalade ──────────────────────────────────────────────────────────────────

class EscalateBody(BaseModel):
    reason: str


@router.post("/{id}/escalate", response_model=EscalationResponse, status_code=status.HTTP_201_CREATED)
async def escalate_request(
    id: str,
    body: EscalateBody,
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    svc: RequestService = Depends(_svc),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
    db: AsyncSession = Depends(get_db),
):
    """Escalade d'une demande — enregistrée comme événement workflow_detail (event_type='escalation_manual').

    Le niveau cible n'est plus choisi manuellement : le système détermine seul le
    chef hiérarchique de la personne qui traite le ticket (assignee, ou l'acteur
    lui-même si le ticket n'est pas encore assigné) et lui réassigne le ticket.
    """
    # Escalade mise de côté (harmonisation statuts/notifications, 2026-08) —
    # fonctionnalité désactivée en attente de réintroduction ultérieure (cf.
    # CLAUDE.md §12). Ne pas réactiver sans consigne explicite.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="La fonctionnalité d'escalade est actuellement désactivée.",
    )

    from sqlalchemy import select as sa_select
    from api.models.ModelAccount import Account
    from api.services.ServiceEscalade import find_hierarchical_chief
    from api.services.NotificationEmitter import emit as emit_notif

    actor_id = str(actor.id)
    req = await svc.get_by_id(id)
    await _resolve_access(actor, req, db)
    if not body.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Le motif d'escalade est obligatoire.",
        )
    assert_ticket_action(actor, req, "escalate", target_status="escalated")
    assert_escalation_allowed(actor, req)
    wf = await wf_repo.find_active_workflow(id)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun workflow actif pour cette demande — impossible d'escalader.",
        )

    handler_id = int(req.assignee_id) if req.assignee_id else int(actor.id)
    if req.assignee_id and str(req.assignee_id) != str(actor.id):
        handler_row = await db.execute(
            sa_select(Account.unity_id).where(Account.id == handler_id)
        )
        handler_unity_id = handler_row.scalar_one_or_none()
    else:
        handler_unity_id = actor.unity_id

    chief_id = await find_hierarchical_chief(
        db, handler_unity_id, exclude_account_id=handler_id,
        exclude_requester_id=req.requester_id,
    )
    if chief_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun chef hiérarchique trouvé pour escalader cette demande automatiquement.",
        )

    chief_row = await db.execute(
        sa_select(Account.name, Account.firstname, Account.role).where(Account.id == chief_id)
    )
    chief_name_raw, chief_firstname, chief_role = chief_row.first()
    chief_name = f"{chief_firstname} {chief_name_raw}".strip() if chief_firstname else chief_name_raw

    event = await detail_repo.create_event({
        "workflow_id": str(wf.id),
        "event_type": "escalation_manual",
        "label": f"Escalade vers {chief_name} — {req.ref}",
        "actor_id": actor_id,
        "actor_name": actor.name,
        "comment": body.reason.strip(),
        "activated": True,
        "infos": {
            "to_user_id": str(chief_id),
            "to_agent_name": chief_name,
            "priority": req.priority,
            "status": "open",
            "event_status": "escalated",
            "source_role": actor.role,
            "actor_role": actor.role,
            "target_user_id": str(chief_id),
            "target_user_name": chief_name,
            "target_role": chief_role,
            "old_status": req.request_status,
            "new_status": "escalated",
        },
    })
    await svc.update(
        id,
        {"request_status": "escalated", "assignee_id": str(chief_id)},
        actor_id=actor_id,
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
    )

    await emit_notif(
        svc.session,
        recipient_id=str(chief_id),
        title=f"Ticket escaladé — {req.ref}",
        body=f"Le ticket {req.ref} vous a été escaladé par {actor.name} : {body.reason.strip()[:100]}",
        type="warning",
        request_id=str(req.id),
        action_label="Voir le ticket",
        action_url=f"/app/requests/{req.id}",
    )

    return EscalationResponse.from_detail(event, int(req.id), req.ref)


class EscalateToDirectorBody(BaseModel):
    reason: str


@router.post(
    "/{id}/escalate-to-director",
    response_model=EscalationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def escalate_to_director_request(
    id: str,
    body: EscalateToDirectorBody,
    actor=Depends(require_roles("chief-departement")),
    svc: RequestService = Depends(_svc),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
    db: AsyncSession = Depends(get_db),
):
    """Escalade exceptionnelle (Lot 3.3) — reservee au chef de departement. Contrairement
    a /escalate (qui cible le chef hierarchique le plus proche via find_hierarchical_chief),
    cette action court-circuite volontairement la hierarchie normale et cible directement
    le directeur de la direction du chef de departement. Motif obligatoire.
    """
    # Escalade mise de côté (harmonisation statuts/notifications, 2026-08) —
    # fonctionnalité désactivée en attente de réintroduction ultérieure (cf.
    # CLAUDE.md §12). Ne pas réactiver sans consigne explicite.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="La fonctionnalité d'escalade est actuellement désactivée.",
    )

    from sqlalchemy import select as sa_select
    from api.models.ModelAccount import Account
    from api.services.ServiceEscalade import find_director_for_department
    from api.services.NotificationEmitter import emit as emit_notif

    actor_id = str(actor.id)
    req = await svc.get_by_id(id)
    await _resolve_access(actor, req, db)
    assert_exceptional_escalation_reason(body.reason)
    assert_ticket_action(actor, req, "escalate_to_director", target_status="escalated")
    wf = await wf_repo.find_active_workflow(id)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun workflow actif pour cette demande — impossible d'escalader.",
        )

    director_id = await find_director_for_department(db, actor.unity_id)
    if director_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun directeur trouvé pour la direction de ce département.",
        )

    director_row = await db.execute(
        sa_select(Account.name, Account.firstname, Account.role).where(Account.id == director_id)
    )
    director_name_raw, director_firstname, director_role = director_row.first()
    director_name = f"{director_firstname} {director_name_raw}".strip() if director_firstname else director_name_raw

    event = await detail_repo.create_event({
        "workflow_id": str(wf.id),
        "event_type": "escalation_exceptional",
        "label": f"Escalade exceptionnelle vers {director_name} — {req.ref}",
        "actor_id": actor_id,
        "actor_name": actor.name,
        "comment": body.reason.strip(),
        "activated": True,
        "infos": {
            "escalation_type": "exceptional",
            "to_user_id": str(director_id),
            "to_agent_name": director_name,
            "priority": req.priority,
            "status": "open",
            "event_status": "escalated",
            "source_role": actor.role,
            "actor_role": actor.role,
            "target_user_id": str(director_id),
            "target_user_name": director_name,
            "target_role": director_role,
            "old_status": req.request_status,
            "new_status": "escalated",
        },
    })
    await svc.update(
        id,
        {"request_status": "escalated", "assignee_id": str(director_id)},
        actor_id=actor_id,
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
    )

    await emit_notif(
        svc.session,
        recipient_id=str(director_id),
        title=f"Escalade exceptionnelle — {req.ref}",
        body=f"Le ticket {req.ref} vous a été escaladé directement par {actor.name} (chef de département) : {body.reason.strip()[:100]}",
        type="warning",
        request_id=str(req.id),
        action_label="Voir le ticket",
        action_url=f"/app/requests/{req.id}",
    )

    return EscalationResponse.from_detail(event, int(req.id), req.ref)


# ── Comments (nested — stockés dans workflow_detail, event_type='comment') ───

class _CommentBody(BaseModel):
    body: str
    is_public: bool = False
    attachment_id: Optional[str] = None
    is_directive: bool = False
    reply_to_id: Optional[str] = None
    peer_id: Optional[str] = None


@router.get("/{request_id}/comments", response_model=list[WorkflowDetailResponse])
async def list_comments(
    request_id: str,
    peer_id: Optional[str] = Query(None, description="Filtre sur une conversation précise (peer_id)."),
    actor=Depends(get_current_user),
    repo: WorkflowDetailRepository = Depends(_detail_repo),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """C-05 / BR-MESSAGING-PAIR-001 — liste les conversations privées par paire du
    ticket dont `actor` fait partie (demandeur, ou intervenant courant/passé sur
    sa propre conversation) ; admin garde une vue de supervision lecture seule
    sur toutes les conversations. `peer_id` restreint à une conversation précise."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    events = await repo.list_comments_by_request(request_id)
    responses = [WorkflowDetailResponse.from_orm(e) for e in events]
    visible = _visible_comment_responses(responses, req, actor)
    if peer_id:
        visible = [ev for ev in visible if str((ev.infos or {}).get("peer_id")) == str(peer_id)]
    return visible


@router.post("/{request_id}/comments", response_model=WorkflowDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    request_id: str,
    body: _CommentBody,
    actor=Depends(get_current_user),
    req_svc: RequestService = Depends(_svc),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
    att_svc: AttachmentService = Depends(_att_svc),
    db: AsyncSession = Depends(get_db),
):
    """C-05 — author_id et author_name forcés depuis le JWT.
    Crée un événement event_type='comment' dans le workflow_detail de la demande.
    Un attachment_id optionnel (déjà uploadé sur cette demande) rattache une pièce
    jointe au commentaire — envoyés en un seul geste comme sur WhatsApp."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    if req.deleted_at is not None or req.request_status in {"closed", "rejected", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Impossible d'écrire un message : la demande est clôturée, rejetée, annulée ou archivée.",
        )
    wf = await wf_repo.find_active_workflow(request_id)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun workflow actif pour cette demande.",
        )

    # Lot 2.7 — "Directive" : commentaire dedie chef -> agent assigne, cible et
    # notifie precisement (BR-NOTIF-001 : jamais tout un service par defaut).
    if body.is_directive:
        if normalize_role(actor.role) not in {"chief-service", "chief-departement"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seul un chef de service ou de département peut envoyer une directive.",
            )
        if not getattr(req, "assignee_id", None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Impossible d'envoyer une directive : ce ticket n'a pas encore d'agent assigné.",
            )
        peer_id = str(req.assignee_id)
    else:
        # BR-MESSAGING-PAIR-001 — la messagerie normale est une conversation
        # strictement privée entre le demandeur et l'INTERVENANT COURANT du
        # ticket (assignee_id). Un ancien intervenant (réaffectation) garde la
        # lecture de sa conversation mais ne peut plus y écrire ; personne
        # d'autre, même avec un accès RBAC large au ticket (`_resolve_access`),
        # ne peut écrire ici.
        requester_id = getattr(req, "requester_id", None)
        assignee_id = getattr(req, "assignee_id", None)
        if not assignee_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Impossible d'écrire : ce ticket n'a pas encore d'intervenant assigné.",
            )
        actor_id_str = str(actor.id)
        if actor_id_str not in {str(requester_id), str(assignee_id)}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seuls le demandeur et l'intervenant actuel de ce ticket peuvent écrire dans cette conversation.",
            )
        # `peer_id` est la clé stable de la conversation — toujours le côté
        # "intervenant" de la paire {demandeur, assigné}, quel que soit lequel
        # des deux écrit. Ne PAS l'inverser selon l'auteur : un message du
        # demandeur et la réponse de l'assigné doivent porter le même peer_id
        # pour rester dans le même fil (sinon ils se retrouvent dans deux
        # conversations distinctes côté lecture/regroupement).
        if not body.peer_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="peer_id requis : indiquez la conversation cible.",
            )
        if str(body.peer_id) != str(assignee_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Conversation invalide : peer_id doit être l'intervenant actuel du ticket.",
            )
        peer_id = str(assignee_id)

    attachment_infos: dict = {}
    if body.attachment_id is not None:
        att = await att_svc.get_by_id(body.attachment_id)
        if str(att.request_id) != str(request_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cette pièce jointe n'appartient pas à cette demande.",
            )
        attachment_infos = {
            "attachment_id": str(att.id),
            "filename": att.filename,
            "mime_type": att.mime_type,
            "size_bytes": att.size_bytes,
        }

    # C-05.1 — reply_to_id : lien reel vers le commentaire cible (fil de discussion),
    # distinct de workflow_detail.parent_id qui reste reserve au chainage d'audit du
    # workflow et a la hierarchie des etapes de traitement.
    reply_infos: dict = {}
    if body.reply_to_id is not None:
        try:
            target_comment = await detail_repo.get_comment_by_id_for_request(
                body.reply_to_id, request_id
            )
        except (ValueError, TypeError):
            target_comment = None
        if target_comment is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Commentaire cible introuvable pour cette demande.",
            )
        reply_infos = {"reply_to_id": str(target_comment.id)}

    directive_target_id = str(req.assignee_id) if body.is_directive else None
    # BR-TRACE-001 — rattache le commentaire à l'intervention ouverte de son auteur,
    # s'il est l'intervenant courant du ticket (sinon reste hors conteneur — ex.
    # message du demandeur).
    intervention_infos = RequestService._intervention_meta_for_actor(
        req.infos, req.assignee_id, actor.id
    )
    event = await detail_repo.create_event({
        "workflow_id": str(wf.id),
        "event_type": "comment_added",
        "label": "Directive envoyée à l'agent" if body.is_directive
            else ("Commentaire public ajouté" if body.is_public else "Commentaire interne ajouté"),
        "actor_id": actor.id,
        "actor_name": _actor_display_name(actor) or actor.name,
        "comment": body.body,
        "activated": True,
        "infos": {
            "is_public": body.is_public,
            "visibility": "public" if body.is_public else "internal",
            "event_status": req.request_status,
            "request_status": req.request_status,
            "source_role": actor.role,
            "actor_role": actor.role,
            "peer_id": peer_id,
            **({"is_directive": True, "target_user_id": directive_target_id} if body.is_directive else {}),
            **attachment_infos,
            **reply_infos,
            **intervention_infos,
        },
    })

    # BR-NOTIFICATION-WORKFLOW-001 §11 — commentaire du demandeur → informe
    # principalement l'intervenant actuel (généralisé au-delà du seul statut
    # `pending` : la règle est "le demandeur écrit", pas "le ticket est en
    # attente"). Ne jamais notifier l'auteur de sa propre action.
    if (
        actor.role == "user"
        and str(getattr(req, "requester_id", "")) == str(actor.id)
        and not body.is_directive
    ):
        assignee_id = getattr(req, "assignee_id", None)
        if assignee_id and str(assignee_id) != str(actor.id):
            from api.services.NotificationEmitter import emit as emit_notif
            await emit_notif(
                db,
                recipient_id=str(assignee_id),
                title="Réponse du demandeur",
                body=f"Le demandeur a répondu sur le ticket {req.ref}.",
                type="info",
                request_id=request_id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{request_id}",
            )

    # BR-NOTIFICATION-WORKFLOW-001 §11 — commentaire de l'intervenant actuel
    # destiné au demandeur : réutilise le marqueur existant `is_public` (visible
    # citoyen) comme signal explicite d'intention, plutôt que de deviner.
    # App-only (pas d'email systématique, pour éviter le bruit).
    elif (
        body.is_public
        and not body.is_directive
        and getattr(req, "assignee_id", None)
        and str(req.assignee_id) == str(actor.id)
        and getattr(req, "requester_id", None)
        and str(req.requester_id) != str(actor.id)
    ):
        from api.services.NotificationEmitter import emit as emit_notif
        await emit_notif(
            db,
            recipient_id=str(req.requester_id),
            title="Nouveau message sur votre ticket",
            body=f"L'intervenant a ajouté un message sur votre ticket {req.ref}.",
            type="info",
            request_id=request_id,
            action_label="Voir le ticket",
            action_url=f"/app/requests/{request_id}",
            send_email=False,
        )

    # Directive : notification nominative a l'agent assigne uniquement (BR-NOTIF-001).
    if directive_target_id:
        from api.services.NotificationEmitter import emit as emit_notif
        await emit_notif(
            db,
            recipient_id=directive_target_id,
            title="Directive reçue",
            body=f"{_actor_display_name(actor) or actor.name} vous a envoyé une directive sur le ticket {req.ref}.",
            type="warning",
            request_id=request_id,
            action_label="Voir le ticket",
            action_url=f"/app/requests/{request_id}",
        )

    return event


@router.delete("/{request_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    request_id: str,
    comment_id: str,
    actor=Depends(get_current_user),
    req_svc: RequestService = Depends(_svc),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    db: AsyncSession = Depends(get_db),
):
    """C-05 / BR-MESSAGING-PAIR-001 — ownership stricte : seul l'auteur (ou
    l'admin, en supervision) peut supprimer un message. Un intervenant d'une
    autre conversation sur ce ticket ne doit plus pouvoir en supprimer les
    messages, cohérent avec le fait qu'il ne peut même plus les lire."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    if req.deleted_at is not None or req.request_status in {"closed", "rejected", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Impossible de supprimer un commentaire : la demande est clôturée, rejetée, annulée ou archivée.",
        )
    entry = await detail_repo.get_by_id(comment_id)
    if entry is None or entry.event_type != "comment_added":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Commentaire introuvable.")
    if normalize_role(actor.role) != "admin" and str(entry.agent_id) != str(actor.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous ne pouvez supprimer que vos propres messages.",
        )
    await detail_repo.delete(comment_id)


# ── Timeline (nested) ─────────────────────────────────────────────────────────

@router.get("/{request_id}/timeline", response_model=list[WorkflowDetailResponse])
async def list_timeline(
    request_id: str,
    actor=Depends(get_current_user),
    repo: WorkflowDetailRepository = Depends(_detail_repo),
    svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    req = await svc.get_by_id(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    await _resolve_access(actor, req, db)
    return await repo.list_by_request(request_id)


class _TimelineEventBody(BaseModel):
    event_type: str
    label: str


@router.post("/{request_id}/timeline", response_model=WorkflowDetailResponse, status_code=status.HTTP_201_CREATED)
async def add_timeline_event(
    request_id: str,
    body: _TimelineEventBody,
    actor=Depends(require_roles("agent-support", "chief-service", "chief-departement", "director", "admin")),
    repo: WorkflowDetailRepository = Depends(_detail_repo),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
):
    """C-06 — injection de timeline réservée au staff (pas les citoyens)."""
    wf = await wf_repo.find_active_workflow(request_id)
    if wf is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Aucun workflow actif pour cette demande.",
        )
    return await repo.create_event({
        "workflow_id": str(wf.id),
        "event_type": body.event_type,
        "label": body.label,
        "actor_id": actor.id,
        "actor_name": _actor_display_name(actor) or actor.name,
        "activated": True,
        "infos": {
            "source_role": actor.role,
            "actor_role": actor.role,
        },
    })


# ── Pièces jointes (nested) ───────────────────────────────────────────────────

@router.get("/{request_id}/attachments", response_model=List[AttachmentResponse])
async def list_attachments(
    request_id: str,
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_att_svc),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """C-N°4 — ownership check avant de lister les pièces jointes."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    result = await svc.list_by_request(request_id, page=1, limit=100)
    items = result.items if hasattr(result, "items") else []
    responses = []
    for item in items:
        resp = AttachmentResponse.from_orm(item)
        resp.storage_path = storage.presigned_url(item.storage_path)
        responses.append(resp)
    return responses


@router.post(
    "/{request_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    request_id: str,
    file: UploadFile = File(...),
    skip_timeline_event: bool = Query(
        False,
        description="Ne pas créer d'événement `attachment_added` séparé — utilisé quand la pièce jointe est immédiatement rattachée à un commentaire (envoi combiné).",
    ),
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_att_svc),
    req_svc: RequestService = Depends(_svc),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload une pièce jointe (multipart/form-data).
    Contraintes : jpg/png/webp/pdf · max 10 Mo · max 5 par demande.

    Sécurité :
      C-04  — uploader_id forcé depuis JWT
      C-N°1 — validation par magic bytes (Content-Type client ignoré)
      C-N°2 — scan ClamAV avant sauvegarde (si CLAMAV_ENABLED=True)
      C-N°4 — ownership check : seuls les acteurs dans le périmètre peuvent uploader
    """
    # C-N°4 — vérifier que l'acteur a accès à cette demande
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)

    # Lire les données brutes (nécessaire pour magic bytes + ClamAV)
    data = await file.read()

    # C-N°1 — validation par magic bytes ; lève HTTP 422 si invalide / spoofé
    declared_mime = file.content_type or "application/octet-stream"
    if declared_mime not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=422,
            detail=f"Type de fichier non autorisé : {declared_mime}. Autorisés : jpeg, png, webp, pdf.",
        )
    real_mime = validate_file_magic_bytes(data, declared_mime)

    # Valider la taille
    if len(data) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Fichier trop volumineux ({len(data) // 1024} Ko). Maximum : 10 Mo.",
        )

    # Vérifier le nombre de fichiers existants
    existing = await svc.list_by_request(request_id, page=1, limit=100)
    count = existing.total if hasattr(existing, "total") else 0
    if count >= _MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {_MAX_FILES_PER_REQUEST} pièces jointes par demande.",
        )

    # C-N°2 — scan antivirus ClamAV
    scan_result = await clamav_scan(data)
    if scan_result.status == "infected":
        raise HTTPException(
            status_code=422,
            detail=f"Fichier rejeté — menace détectée : {scan_result.threat_name}.",
        )
    scan_db_status = scan_result.status  # "clean" | "scan_error"

    # Sauvegarder (storage_path généré côté serveur — jamais fourni par le client)
    storage_path, _ = storage.save_file(data, file.filename or "fichier", request_id)

    att = await svc.create({
        "request_id": request_id,
        "uploader_id": actor.id,       # C-04 — forcé depuis JWT
        "filename": file.filename or "fichier",
        "storage_path": storage_path,
        "mime_type": real_mime,        # C-N°1 — MIME validé par magic bytes
        "size_bytes": len(data),
        "scan_status": scan_db_status, # C-N°2 — résultat ClamAV
    })

    if not skip_timeline_event:
        wf = await _timeline_workflow(wf_repo, request_id)
        if wf is not None:
            # BR-TRACE-001 — rattache la pièce jointe à l'intervention ouverte de son
            # auteur, s'il est l'intervenant courant du ticket.
            intervention_infos = RequestService._intervention_meta_for_actor(
                req.infos, req.assignee_id, actor.id
            )
            await detail_repo.create_event({
                "workflow_id": str(wf.id),
                "event_type": "attachment_added",
                "label": f"Pièce jointe ajoutée — {att.filename}",
                "actor_id": actor.id,
                "actor_name": _actor_display_name(actor) or actor.name,
                "activated": True,
                "infos": {
                    "event_status": req.request_status,
                    "request_status": req.request_status,
                    "source_role": actor.role,
                    "actor_role": actor.role,
                    "attachment_id": str(att.id),
                    "filename": att.filename,
                    "mime_type": real_mime,
                    "size_bytes": len(data),
                    "scan_status": scan_db_status,
                    **intervention_infos,
                },
            })

    resp = AttachmentResponse.from_orm(att)
    resp.storage_path = storage.presigned_url(storage_path)
    return resp


@router.delete("/{request_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    request_id: str,
    attachment_id: str,
    actor=Depends(get_current_user),
    svc: AttachmentService = Depends(_att_svc),
    req_svc: RequestService = Depends(_svc),
    wf_repo: WorkflowRepository = Depends(_wf_repo),
    detail_repo: WorkflowDetailRepository = Depends(_detail_repo),
    db: AsyncSession = Depends(get_db),
):
    """C-N°4 — ownership check avant suppression d'une pièce jointe."""
    req = await req_svc.get_by_id(request_id)
    await _resolve_access(actor, req, db)
    att = await svc.get_by_id(attachment_id)
    if str(att.request_id) != str(request_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pièce jointe introuvable.")

    filename = att.filename
    mime_type = att.mime_type
    size_bytes = att.size_bytes
    scan_status = att.scan_status
    storage.delete_file(att.storage_path)
    await svc.delete(attachment_id)

    wf = await _timeline_workflow(wf_repo, request_id)
    if wf is not None:
        await detail_repo.create_event({
            "workflow_id": str(wf.id),
            "event_type": "attachment_deleted",
            "label": f"Pièce jointe supprimée — {filename}",
            "actor_id": actor.id,
            "actor_name": _actor_display_name(actor) or actor.name,
            "activated": True,
            "infos": {
                "event_status": req.request_status,
                "request_status": req.request_status,
                "source_role": actor.role,
                "actor_role": actor.role,
                "attachment_id": str(attachment_id),
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "scan_status": scan_status,
            },
        })


# ── Téléchargement fichiers locaux ────────────────────────────────────────────

@router.get("/download/{path:path}")
async def download_file(
    path: str,
    actor=Depends(get_current_user),
    req_svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """
    Sert les fichiers uploadés localement.
    C-N°4 — ownership check : extrait request_id depuis le chemin de stockage
    (format : requests/{request_id}/{uuid}_{filename}).
    """
    # Empêcher la traversée de répertoires
    uploads_dir = Path(__file__).parent.parent.parent / "uploads"
    full = (uploads_dir / path).resolve()
    if not str(full).startswith(str(uploads_dir.resolve())):
        raise HTTPException(status_code=400, detail="Chemin invalide.")
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")

    # Extraire request_id depuis le chemin stocké (requests/<id>/...)
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 3 and parts[0] == "requests":
        request_id_from_path = parts[1]
        try:
            req = await req_svc.get_by_id(request_id_from_path)
            await _resolve_access(actor, req, db)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=403, detail="Accès refusé à ce fichier.")
    # Si le chemin ne correspond pas au format attendu, refuser par défaut
    elif normalize_role(actor.role) != "admin":
        raise HTTPException(status_code=403, detail="Accès refusé à ce fichier.")

    return FileResponse(str(full))


# ── Suppression avec vérification UUID (pattern edgrh DELETE /{id}/{uuid}) ────

@router.delete(
    "/{id}/{uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Suppression avec vérification UUID — pattern edgrh delete_uuid()",
    description="Double vérification id + uuid avant soft-delete. Réservé admin.",
)
async def delete_request_uuid(
    id: str,
    uuid: str,
    _=Depends(require_roles("admin")),
    svc: RequestService = Depends(_svc),
):
    await svc.delete_by_uuid(id, uuid)


# ── Restauration soft-delete (pattern edgrh PUT /restore/{id}) ────────────────

@router.put(
    "/{id}/restore",
    response_model=RequestResponse,
    summary="Restaurer une demande soft-deleted — pattern edgrh /restore/{id}",
)
async def restore_request(
    id: str,
    _=Depends(require_roles("admin")),
    svc: RequestService = Depends(_svc),
):
    return await svc.restore(id)
