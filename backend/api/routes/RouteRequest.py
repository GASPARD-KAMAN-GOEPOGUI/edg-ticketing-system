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
from api.schemas.SchemaRequest import RequestCreate, RequestWorkflowCreate, RequestUpdate, RequestResponse, RequestListItemResponse, DistributionListItemResponse, PvTrackingItemResponse, RequestSearch
from api.schemas.SchemaWorkflowDetail import WorkflowDetailResponse
from api.schemas.SchemaAttachment import AttachmentResponse
from pydantic import BaseModel
from api.schemas.base import PaginatedResponse
from api.services import RequestService, AttachmentService, RequestExportService, PvInterventionService
from api.services.ServiceExport import build_response
from api.repositories import WorkflowDetailRepository, WorkflowRepository
from api.services.ServiceClamAV import scan_bytes as clamav_scan
from api.core.ticket_actions import (
    TREATING_ROLES,
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


def _check_request_access(
    actor,
    req,
    allowed_dir_unity_ids: set[int] | None = None,
    *,
    read_only: bool = False,
) -> None:
    """
    Vérifie que l'acteur a le droit d'accéder à la demande `req`.
    Lève HTTP 403 si l'acteur est hors périmètre.

    Politique d'accès :
      tout rôle        → ses propres demandes en lecture personnelle
      tout rôle        → les demandes qui lui sont personnellement assignées (assignee_id),
                         même hors de son unité courante (BR-ROLE-AGENT-001, routage direct)
      user             → uniquement ses propres demandes
      chief-service / technicien / chef-division-support
                       → demandes de leur unité (service) uniquement
      chief-service    → + LECTURE de toute demande encore dans la File d'attente
                         (`read_only=True`, voir ci-dessous)
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

    # File d'attente — un ticket non encore qualifie n'a pas d'unite traitante
    # (`unity_id IS NULL`) ni d'assigne : aucun perimetre d'unite ne peut donc
    # l'autoriser, et le chef de service se voyait refuser la fiche du ticket
    # qu'il doit justement qualifier (notification « Nouveau ticket a
    # qualifier » → « Ticket introuvable »). La LECTURE s'aligne donc sur les
    # droits deja accordes a la File d'attente elle-meme : `_queue_manage_guard`
    # ouvre la liste de triage et la qualification au chef de service et a
    # l'admin sans borne d'unite.
    #
    # `read_only` est indispensable : cette fonction garde aussi les mutations
    # (PUT /requests/{id} notamment). Sans le drapeau, tout ticket etant cree
    # `in_triage=True`, n'importe quel chef de service hors perimetre pourrait
    # le modifier — exactement le verrou du Lot 2.1
    # (test_patch_blocks_staff_outside_perimeter). L'ecriture reste donc bornee
    # a l'unite, et passe par la route dediee `/qualify`, gardee a part.
    if read_only and role == "chief-service" and getattr(req, "in_triage", False):
        return

    if role in {"chief-service", "technicien", "chef-division-support"}:
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


async def _resolve_access(actor, req, db: AsyncSession, *, read_only: bool = False) -> None:
    """Wrapper async : pré-calcule les unity_ids autorisés puis vérifie l'accès.

    `read_only=True` sur les seules routes de consultation (voir
    `_check_request_access`) — jamais sur une route qui écrit."""
    # Les deux seuls roles qui beneficiaient d'un perimetre elargi
    # (chief-departement, director) ont ete retires le 2026-09-25 : les roles
    # operationnels restants sont bornes a leur propre unite.
    _check_request_access(actor, req, None, read_only=read_only)


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

    if role in {"chief-service", "technicien", "chef-division-support"}:
        if actor.unity_id and int(actor.unity_id) == requested_unity_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé : cette unité n'est pas dans votre périmètre.",
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


def _pv_svc(db: AsyncSession = Depends(get_db)) -> PvInterventionService:
    return PvInterventionService(db)


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
    # La messagerie a ete retiree de l'application (2026-09-25). Les evenements
    # `comment_added` deja enregistres RESTENT en base — c'est de l'historique,
    # on ne detruit pas des donnees — mais ils ne sortent plus par l'API : le
    # filtrage par paire ayant disparu avec la fonctionnalite, les laisser
    # passer rendrait d'anciennes conversations privees visibles de tout le staff.
    schema = schema.copy(update={
        "timelines": [e for e in schema.timelines if e.event_type != "comment_added"],
    })
    return await _attach_participant_avatars(schema, svc)


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
    scope_actor_id: Optional[str] = None
    if is_own_view or is_own_assignee_view:
        pass  # requester_id/assignee_id = actor.id suffit ; unit/direction non forcés
    elif actor_role == "user":
        requester_id = str(actor.id)           # toujours ses propres demandes
    elif actor_role in {"chief-service", "technicien", "chef-division-support"}:
        if actor.unity_id:
            unit_id = str(actor.unity_id)       # forcé, ignore le paramètre client
            direction_id = None
            # BR-REQUESTER-NEVER-LOSES-001 — le périmètre devient « mon unité OU
            # je suis demandeur OU je suis assigné ». Sans ce OU, un membre du
            # staff qui dépose une demande la perdait dès qu'elle était traitée
            # hors de son unité, ou que l'unité traitante du ticket n'était pas
            # renseignée : absente de l'historique (scopé unité) comme de Ma
            # boîte (qui exclut les tickets dont on est le demandeur).
            scope_actor_id = str(actor.id)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte non rattaché à une unité. Contactez un administrateur.",
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
            scope_actor_id=scope_actor_id,
            sla_breached=sla_breached,
            in_triage=in_triage,
            search=search,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
    return await svc.list_all(page=page, limit=limit)


_staff = Depends(require_roles("chief-service", "admin"))


async def _queue_manage_guard(actor=Depends(get_current_user)):
    """Garde stricte (sans expansion d'alias RBAC) — la gestion de la File d'attente
    (liste de triage + qualification) est reservee au chef de service (CSSHF) et a
    l'admin uniquement. Volontairement plus etroite que require_roles("chief-service", ...),
    qui via ROLE_GROUP_ALIASES donnerait aussi acces a technicien/chef-division-support."""
    if normalize_role(actor.role) not in {"chief-service", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé au chef de service et à l'administrateur.",
        )
    return actor


async def _distribution_guard(actor=Depends(get_current_user)):
    """BR-DISTRIBUTION-001 — garde stricte (sans expansion d'alias RBAC) : la file
    "Distribution" est l'espace propre du chef de division support. L'admin y accede
    aussi (role bypass habituel). Tout autre role est refuse — y compris chief-service
    et technicien, que l'alias RBAC laisserait passer avec require_roles()."""
    if normalize_role(actor.role) not in {"chef-division-support", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé au chef de division support.",
        )
    return actor


async def _treating_roles_guard(actor=Depends(get_current_user)):
    """Garde stricte (sans expansion d'alias RBAC) des espaces de traitement.

    Reserve aux roles qui prennent effectivement un ticket en charge — les
    `TREATING_ROLES` — plus l'admin, qui traite aussi des tickets. Le demandeur
    en est exclu : il suit ses propres demandes depuis son espace personnel."""
    if normalize_role(actor.role) not in TREATING_ROLES | {"admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux intervenants du support.",
        )
    return actor


@router.get("/resolved-by-me", response_model=PaginatedResponse[RequestListItemResponse])
async def list_resolved_by_me(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(_treating_roles_guard),
    svc: RequestService = Depends(_svc),
):
    """Onglet « Tickets résolus » — les tickets dont l'intervenant connecté est
    l'intervenant courant et dont le traitement est terminé (`resolved` ou
    `closed`).

    Le périmètre est forcé depuis l'acteur authentifié : aucun paramètre client
    ne permet de consulter les tickets résolus par quelqu'un d'autre."""
    return await svc.list_resolved_by(str(actor.id), page=page, limit=limit)


@router.get("/distribution", response_model=PaginatedResponse[DistributionListItemResponse])
async def list_distribution(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(_distribution_guard),
    svc: RequestService = Depends(_svc),
):
    """File "Distribution" — uniquement les tickets orientes vers CE chef de division
    et pas encore repartis. Le perimetre est force depuis l'acteur authentifie : aucun
    parametre client ne permet de consulter la distribution d'un autre CDS."""
    return await svc.list_distribution(str(actor.id), page=page, limit=limit)


@router.get("/pv-tracking", response_model=PaginatedResponse[PvTrackingItemResponse])
async def list_pv_tracking(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    actor=Depends(_distribution_guard),
    svc: RequestService = Depends(_svc),
):
    """TSI — Tableau de Suivi des Interventions, livrable de la tâche 3.4.

    Le chef de division y suit les tickets qu'il a répartis jusqu'à l'archivage
    de leur PV. Le périmètre est déduit de son identité (`distributor_id`),
    jamais d'un paramètre client. À ne pas confondre avec
    `GET /reports/interventions`, qui agrège des statistiques."""
    return await svc.list_pv_tracking(str(actor.id), page=page, limit=limit)


@router.post("/{id}/distribution/take", response_model=RequestResponse)
async def distribution_take(
    id: str,
    actor=Depends(_distribution_guard),
    svc: RequestService = Depends(_svc),
):
    """Le chef de division prend lui-meme le ticket : il devient responsable
    operationnel et le ticket rejoint sa boite de traitement."""
    return await svc.distribution_take(
        id, actor=actor, actor_name=_actor_display_name(actor),
    )


class DistributionAssignBody(BaseModel):
    technician_id: str


@router.post("/{id}/distribution/assign", response_model=RequestResponse)
async def distribution_assign(
    id: str,
    body: DistributionAssignBody,
    actor=Depends(_distribution_guard),
    svc: RequestService = Depends(_svc),
):
    """Le chef de division assigne le ticket a un technicien de SA division."""
    return await svc.distribution_assign(
        id, body.technician_id, actor=actor, actor_name=_actor_display_name(actor),
    )


@router.get("/distribution/technicians")
async def list_distribution_technicians(
    actor=Depends(_distribution_guard),
    db: AsyncSession = Depends(get_db),
):
    """Techniciens actifs de la division du chef de division — destinataires valides.

    Endpoint metier dedie : le frontend n'a jamais a charger tous les utilisateurs
    puis filtrer. Le filtre sur le role est STRICT (pas d'expansion de groupe RBAC,
    contrairement a RepositoryAccount._role_filter)."""
    if normalize_role(actor.role) != "admin" and not actor.unity_id:
        return []
    stmt = (
        select(Account.id, Account.name, Account.firstname, Account.email, Account.avatar_url)
        .where(Account.role == "technicien")
        .where(Account.account_status == "active")
        .where(Account.deleted_at.is_(None))
    )
    if actor.unity_id:
        stmt = stmt.where(Account.unity_id == int(actor.unity_id))
    rows = await db.execute(stmt.order_by(Account.name))
    return [
        {
            "id": str(r.id),
            "name": " ".join(p for p in [r.firstname, r.name] if p) or r.name,
            "email": r.email,
            "avatar": r.avatar_url,
        }
        for r in rows.all()
    ]


@router.get("/triage", response_model=PaginatedResponse[RequestListItemResponse])
async def list_triage(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _=Depends(_queue_manage_guard),
    svc: RequestService = Depends(_svc),
):
    """Liste de triage (File d'attente) — reservee au chef de service et a l'admin."""
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


_workload_staff = Depends(require_roles("admin"))


@router.get("/workload-by-unit")
async def workload_by_unit(
    unit_id: Optional[str] = Query(None, description="Admin uniquement"),
    direction_id: Optional[str] = Query(None, description="Admin uniquement — expanse departement+services"),
    _staff_guard=_workload_staff,
    db: AsyncSession = Depends(get_db),
    svc: RequestService = Depends(_svc),
):
    """Charge actuelle (tickets non terminaux) par agent assigné — Centre de répartition (Lot 2/3).

    Seul l'admin atteint cet endpoint depuis le retrait du role chef de
    departement (2026-09-25) : les filtres client sont donc toujours acceptes.
    """
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
    actor=Depends(require_roles("chief-service", "admin")),
    svc: RequestService = Depends(_svc),
):
    """File d'attente active — réservée aux agents et supérieurs, filtrée par périmètre."""
    # Forçage RBAC — le paramètre client direction_id est ignoré (C-N°3)
    actor_role = normalize_role(actor.role)
    if actor_role in {"chief-service", "technicien", "chef-division-support"}:
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
    # Procédure EDG/PS-GSI/Pro-02, tâche 1.3 — point de contrôle « descriptif de
    # la solution proposée ». Exigé uniquement à l'imputation vers un chef de
    # division support : c'est cette imputation que le point de contrôle encadre.
    # Quand le CSSHF prend le ticket pour lui-même, il n'y a pas d'imputation.
    proposed_solution: Optional[str] = None


async def _assert_queue_target_allowed(actor, assignee_id: Optional[str], db: AsyncSession) -> bool:
    """Module 2 — depuis la File d'attente, le chef de service n'a que deux issues :
    prendre le ticket pour lui-meme, ou l'envoyer a un chef de division support (CDS)
    de SON service. L'admin n'est pas contraint (role bypass habituel).

    Ne concerne QUE ce point d'entree : la chaine de transmission dynamique qui suit
    (transmit_treatment, A -> An) reste libre et n'est pas touchee.

    Retourne True si la cible est un chef de division support, c'est-a-dire si on
    est bien dans le cas d'une IMPUTATION au sens de la tache 1.3 de la procedure
    (le descriptif de solution proposee y devient alors obligatoire)."""
    if assignee_id is None:
        return False
    if str(assignee_id) == str(actor.id):
        return False  # prise pour son propre traitement : pas une imputation
    if normalize_role(actor.role) == "admin":
        # L'admin n'est pas contraint sur la cible, mais on determine quand meme
        # s'il s'agit d'une imputation a un CDS.
        row = await db.execute(
            select(Account.role).where(Account.id == int(assignee_id))
        )
        return normalize_role(str(row.scalar_one_or_none() or "")) == "chef-division-support"

    row = await db.execute(
        select(Account.role, Account.unity_id).where(Account.id == int(assignee_id))
    )
    target = row.first()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cet intervenant n'existe pas.",
        )
    target_role, target_unity_id = target
    if normalize_role(target_role) != "chef-division-support":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Depuis la file d'attente, un ticket ne peut être envoyé qu'à un chef "
                "de division support de votre service, ou pris pour votre propre traitement."
            ),
        )
    if not actor.unity_id or str(target_unity_id) != str(actor.unity_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce chef de division support n'appartient pas à votre service.",
        )
    return True


@router.post("/{id}/qualify", response_model=RequestResponse)
async def qualify_triage(
    id: str,
    body: QualifyTriageBody,
    actor=Depends(_queue_manage_guard),
    db: AsyncSession = Depends(get_db),
    svc: RequestService = Depends(_svc),
):
    """Qualifie une demande de triage — reservee a la File d'attente (chief-service/admin)."""
    is_imputation = await _assert_queue_target_allowed(actor, body.assignee_id, db)
    # Procedure tache 1.3 — le descriptif de solution proposee est le point de
    # controle de l'imputation a un chef de division support. Exige uniquement
    # dans ce cas : une prise pour son propre traitement n'est pas une imputation.
    if is_imputation and not (body.proposed_solution or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Décrivez la solution proposée avant d'orienter ce ticket vers un "
                "chef de division support."
            ),
        )
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
    actor=Depends(require_roles("chief-service", "admin")),
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
    actor=Depends(require_roles("chief-service", "admin")),
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


class ProposedSolutionResponse(BaseModel):
    proposed_solution: Optional[str] = None


# Procédure EDG/PS-GSI/Pro-02, tâche 1.3 — rôles autorisés à LIRE le descriptif
# de solution proposée. Liste explicite plutôt que `require_roles()`, dont
# l'expansion d'alias RBAC rendrait le périmètre implicite.
_PROPOSED_SOLUTION_READERS = {
    "chief-service", "technicien", "chef-division-support", "admin",
}


@router.get("/{id}/proposed-solution", response_model=ProposedSolutionResponse)
async def get_proposed_solution(
    id: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
    db: AsyncSession = Depends(get_db),
):
    """Descriptif de la solution proposée par le chef de service à l'imputation.

    Endpoint séparé, et non un champ de `RequestResponse` : le demandeur ne doit
    jamais voir ce descriptif (piste de travail interne, qui peut se révéler
    fausse au diagnostic terrain), or une vingtaine d'endpoints renvoient un
    `RequestResponse` dont sept lui sont accessibles. Isoler la donnée derrière
    sa propre garde rend la fuite structurellement impossible plutôt que de
    dépendre d'un effacement répété à chaque endpoint.
    """
    if normalize_role(actor.role) not in _PROPOSED_SOLUTION_READERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux intervenants du support.",
        )
    req = await svc.get_by_id(id)
    await _resolve_access(actor, req, db)
    # Un intervenant peut être par ailleurs le demandeur d'un autre ticket ; sur
    # CE ticket-ci, s'il est le demandeur, il n'y a pas accès. L'admin, lui,
    # garde sa visibilité globale de supervision.
    if (
        normalize_role(actor.role) != "admin"
        and str(getattr(req, "requester_id", "") or "") == str(actor.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le descriptif de solution proposée n'est pas accessible au demandeur.",
        )
    return ProposedSolutionResponse(proposed_solution=getattr(req, "proposed_solution", None))


class PvSubmitBody(BaseModel):
    """Pièces jointes facultatives — typiquement le PV signé et scanné, la
    signature étant manuscrite (aucune signature électronique au projet)."""
    attachment_ids: Optional[list[str]] = None


@router.post("/{id}/pv/submit", response_model=RequestResponse)
async def submit_pv_intervention(
    id: str,
    body: PvSubmitBody,
    actor=Depends(require_roles("chief-service", "admin")),
    svc: RequestService = Depends(_svc),
    att_svc: AttachmentService = Depends(_att_svc),
):
    """Tâche 3.3 — « Soumettre le PV d'intervention au Chef de division ».

    Le destinataire n'est pas choisi : c'est le chef de division qui a réparti
    le ticket (`distributor_id`, posé à la tâche 1.4). La liste de rôles n'est
    qu'un filtre général — élargi au technicien par ROLE_GROUP_ALIASES, comme
    `/resolve` ; la vraie garde est « être l'intervenant qui a traité », côté
    service."""
    attachments = await _validate_attachment_ids(att_svc, id, body.attachment_ids)
    return await svc.pv_submit(
        id,
        attachments=attachments,
        actor=actor,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
    )


@router.post("/{id}/pv/archive", response_model=RequestResponse)
async def archive_pv_intervention(
    id: str,
    actor=Depends(_distribution_guard),
    svc: RequestService = Depends(_svc),
):
    """Tâche 3.4 — « Enregistrer et archiver le PV d'intervention ».

    Réservé au chef de division qui a réparti le ticket (l'admin garde son
    bypass). La tâche 3.3 doit avoir eu lieu : on n'archive pas un PV qui n'a
    pas été soumis."""
    return await svc.pv_archive(
        id,
        actor=actor,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
    )


@router.get("/{id}/pv")
async def download_pv_intervention(
    id: str,
    actor=Depends(get_current_user),
    svc: RequestService = Depends(_svc),
    pv_svc: PvInterventionService = Depends(_pv_svc),
    db: AsyncSession = Depends(get_db),
):
    """Procédure EDG/PS-GSI/Pro-02, tâche 3.1 — « Établir le PV d'Intervention »,
    au format officiel EDG/PS-GSI/PV-01.

    Accessible au **demandeur** aussi : c'est lui qui valide le dépannage et
    signe le PV (tâche 3.2). La visibilité est celle du ticket
    (`_resolve_access`), et le PV n'expose pas `proposed_solution` — la seule
    donnée que le demandeur ne doit pas voir.

    Lecture seule : aucun changement de statut, aucune notification, aucun
    événement métier."""
    req = await svc.get_by_id(id)
    await _resolve_access(actor, req, db)
    content, filename = await pv_svc.build(id)
    return build_response(content, "pdf", filename)


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
    actor=Depends(require_roles("user", "chief-service", "admin")),
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
    actor=Depends(require_roles("chief-service", "admin")),
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
    actor=Depends(require_roles("chief-service", "admin")),
    svc: RequestService = Depends(_svc),
    att_svc: AttachmentService = Depends(_att_svc),
):
    """BR-TRANSMIT-001 — "Terminer le traitement". Autorisé à l'intervenant actuel
    (request.assignee_id == actor.id) parmi les rôles traitants. Résumé, solution
    et travail réalisé désormais obligatoires pour tous les rôles."""
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


class FieldCheckBody(BaseModel):
    """Tâche 2.1 — constat d'intervention."""
    conformity: str            # "conforme" | "ecart"
    findings: str
    observed_category: Optional[str] = None
    observed_priority: Optional[str] = None


@router.post("/{id}/field-check", response_model=RequestResponse)
async def field_check_request(
    id: str,
    body: FieldCheckBody,
    actor=Depends(require_roles("chief-service", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Procédure EDG/PS-GSI/Pro-02, tâche 2.1 — « Qualifier la demande »,
    point de contrôle « vérification de l'état réel de la requête ».

    Rien à voir avec `POST /{id}/qualify`, qui est la qualification du chef de
    service depuis la File d'attente (garde stricte `_queue_manage_guard`, dont
    le technicien est volontairement exclu) : ici l'intervenant constate sur le
    terrain avant d'intervenir. La vraie garde n'est donc pas le rôle mais
    `assert_is_current_handler` côté service — la liste de rôles ci-dessus n'est
    qu'un filtre général, élargi au technicien et au chef de division par
    ROLE_GROUP_ALIASES, exactement comme `/resolve` et `/transmit`."""
    return await svc.field_check(
        id,
        conformity=body.conformity,
        findings=body.findings,
        observed_category=body.observed_category,
        observed_priority=body.observed_priority,
        actor=actor,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
    )


class StartTreatmentBody(BaseModel):
    """BR-TRAITEMENT-PROGRESSIF-001 — « Démarrer le traitement ».

    Le corps ne porte QUE le lieu : la date et l'heure de début sont prises côté
    serveur, jamais reçues du navigateur."""
    location: str


@router.post("/{id}/start-treatment", response_model=RequestResponse)
async def start_treatment_request(
    id: str,
    body: StartTreatmentBody,
    actor=Depends(require_roles("chief-service", "admin")),
    svc: RequestService = Depends(_svc),
):
    """Deuxième geste du workflow progressif, entre le constat et la résolution.

    Même garde que `/field-check`, `/resolve` et `/transmit` : la liste de rôles
    n'est qu'un filtre général (élargi au technicien et au chef de division par
    ROLE_GROUP_ALIASES), la vraie garde étant `assert_is_current_handler` côté
    service, complétée par le refus d'un démarrage sans constat ou déjà fait."""
    return await svc.start_treatment(
        id,
        location=body.location,
        actor=actor,
        actor_id=str(actor.id),
        actor_name=_actor_display_name(actor),
        actor_role=actor.role,
    )


class TransmitTreatmentBody(BaseModel):
    to_user_id: str
    work_done: str
    reason: str
    instruction: Optional[str] = None
    attachment_ids: Optional[list[str]] = None


@router.get("/{id}/transmit-targets")
async def list_transmit_targets(
    id: str,
    actor=Depends(require_roles("chief-service", "admin")),
    svc: RequestService = Depends(_svc),
):
    """BR-TRANSMIT-SCOPE-TECH-001 — destinataires possibles pour « Transmettre le
    traitement », calculés par le SERVEUR selon le rôle de l'acteur et le ticket.

    `restricted=true` (technicien) : `items` est la liste fermée de ses cibles —
    ses collègues techniciens du même service, et le responsable qui lui a
    distribué le ticket. Le client affiche alors une sélection au lieu de
    l'annuaire, et masque les filtres direction/département/service.

    `restricted=false` (autres rôles traitants) : annuaire libre, `items` vide.
    """
    return await svc.list_transmit_targets(id, actor=actor)


@router.post("/{id}/transmit", response_model=RequestResponse)
async def transmit_treatment_request(
    id: str,
    body: TransmitTreatmentBody,
    actor=Depends(require_roles("chief-service", "admin")),
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
    """Cloture — demandeur (ses propres tickets resolus) ou role operationnel/admin."""
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
    elif normalize_role(actor.role) not in {"chief-service", "technicien", "chef-division-support", "admin"}:
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
    """Annulation — demandeur (ses propres tickets) ou role operationnel/admin."""
    if actor.role == "user":
        req = await svc.get_by_id(id)
        if req.requester_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez annuler que vos propres demandes.",
            )
    elif normalize_role(actor.role) not in {"chief-service", "technicien", "chef-division-support", "admin"}:
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
    actor=Depends(require_roles("admin")),
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
    actor=Depends(require_roles("admin")),
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
    actor=Depends(require_roles("admin")),
    svc: RequestService = Depends(_svc),
):
    """Réaffectation d'un ticket à un autre service — admin uniquement depuis le
    retrait des rôles chef de département et directeur (2026-09-25)."""
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
    actor=Depends(require_roles("admin")),
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


# ── Comments (nested — stockés dans workflow_detail, event_type='comment') ───

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
    actor=Depends(require_roles("chief-service", "admin")),
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
