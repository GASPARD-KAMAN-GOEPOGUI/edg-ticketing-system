from __future__ import annotations

from typing import Any

from api.core.error_codes import ErrorCode
from api.core.exceptions import BusinessException, ForbiddenException
from api.core.rbac import normalize_role


# CDC §4.1 — matrice unique des transitions de statut.
# Cle = statut cible, valeur = statuts sources autorises.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "qualifying": {"new", "reopened", "qualified", "assigned", "in_progress", "pending", "escalated"},
    "qualified": {"qualifying"},
    "assigned": {"qualified", "qualifying", "new", "reopened"},
    "in_progress": {"assigned", "qualifying", "qualified", "pending", "escalated"},
    "pending": {"in_progress", "assigned"},
    "escalated": {"in_progress", "assigned", "pending", "qualifying"},
    "resolved": {"in_progress", "assigned", "escalated", "pending"},
    "closed": {"resolved"},
    "reopened": {"resolved", "rejected", "closed"},
    "rejected": {"new", "qualifying", "qualified", "assigned", "in_progress", "pending"},
    "cancelled": {"new", "qualifying", "qualified", "assigned", "in_progress", "pending"},
}

BYPASS_TRANSITION_ROLES = frozenset({"admin"})
GLOBAL_SCOPE_ROLES = frozenset({"admin"})
OWN_REQUEST_ALLOWED_ACTIONS = frozenset({"close", "cancel", "request_reopen"})

# BR-TRANSMIT-001 — workflow collaboratif dynamique post-file d'attente. Rôles
# traitants pouvant devenir "intervenant actuel" (request.assignee_id) et donc
# transmettre/terminer un traitement. L'admin n'en fait volontairement pas partie :
# son intervention reste possible mais exceptionnelle (bypass séparé, cf.
# assert_is_current_handler) plutôt qu'un traitement normal.
TREATING_ROLES = frozenset({"agent-support", "chief-service", "chief-departement", "director"})
QUEUE_HANDLER_ROLES = frozenset({"agent-support", "chief-service", "chief-departement", "director", "admin"})
QUEUE_HANDLER_DENY_RAW_ROLES = frozenset({"dg"})
# Statuts compatibles avec une transmission ou une terminaison de traitement — un
# ticket doit déjà être pris en charge activement. Identique à ALLOWED_TRANSITIONS["resolved"].
COLLABORATIVE_STATUSES = frozenset({"assigned", "in_progress", "pending", "escalated"})
STATUS_ALIASES = {
    "cancalled": "cancelled",
    "canceled": "cancelled",
    "escaladed": "escalated",
}
TERMINAL_STATUSES = frozenset({"cancelled", "closed", "resolved", "rejected"})
QUALIFIABLE_STATUSES = frozenset({"new", "qualifying", "qualified", "reopened"})

ACTION_ALLOWED_ROLES: dict[str, set[str]] = {
    "qualify": set(QUEUE_HANDLER_ROLES),
    # Philosophie collaborative : tous les rôles opérationnels peuvent prendre ou
    # assigner un ticket de file d'attente ; le périmètre est contrôlé dans
    # assert_ticket_scope/assert_assignment_allowed.
    "assign": set(QUEUE_HANDLER_ROLES),
    # BR-TRANSMIT-001 (remplace Lot 3.2) : "Terminer le traitement" est desormais ouvert
    # a chief-departement — la restriction "un chef de departement ne traite jamais
    # lui-meme" ne s'applique plus des lors qu'il est devenu intervenant actuel via une
    # transmission (assert_is_current_handler verifie assignee_id == actor.id).
    "resolve": {"agent-support", "chief-service", "chief-departement", "director", "admin"},
    "close": {"user", "agent-support", "chief-service", "chief-departement", "director", "admin"},
    "request_reopen": {"user", "agent-support", "chief-service", "chief-departement", "director", "admin"},
    "reopen": {"chief-service", "chief-departement", "director", "admin"},
    "reject_reopen": {"chief-service", "chief-departement", "director", "admin"},
    "cancel": {"user", "agent-support", "chief-service", "chief-departement", "director", "admin"},
    # Lot 2.5 : "Changer de service" retire a chief-service — reste chief-departement
    # (pilotage multi-services), director (transfert au sein de sa direction) et admin.
    "reassign": {"chief-departement", "director", "admin"},
    "transfer_direction": {"director", "admin"},
    "reject": {"chief-service", "chief-departement", "admin"},
    "escalate": {"agent-support", "chief-service", "chief-departement", "director", "admin"},
    # Lot 3.3 : "Escalade exceptionnelle" — court-circuite find_hierarchical_chief pour
    # cibler directement le directeur. Reservee a chief-departement.
    "escalate_to_director": {"chief-departement"},
    "change_priority": {"chief-service", "chief-departement", "director", "admin"},
    # BR-TRANSMIT-001 : "Transmettre le traitement" — libre parmi les rôles traitants,
    # la vraie garde est assert_is_current_handler (assignee_id == actor.id), le rôle
    # ne sert que de filtre de sécurité général.
    "transmit_treatment": {"agent-support", "chief-service", "chief-departement", "director", "admin"},
}

TRIAGE_SCOPE_ACTIONS = frozenset({"qualify", "resolve"})


def normalize_status(status: str | None) -> str:
    clean = (status or "new").strip().lower()
    return STATUS_ALIASES.get(clean, clean)


def _value(obj: Any, name: str) -> Any:
    return getattr(obj, name, None)


def assert_action_allowed(actor_role: str | None, action: str) -> None:
    allowed = ACTION_ALLOWED_ROLES.get(action)
    raw_role = (actor_role or "").strip().lower()
    role = normalize_role(actor_role)
    if action in {"qualify", "assign"} and raw_role in QUEUE_HANDLER_DENY_RAW_ROLES:
        raise ForbiddenException(
            "Vous n'etes pas autorise a effectuer cette action sur le ticket.",
            error_code=ErrorCode.FORBIDDEN,
        )
    if allowed is None or role not in allowed:
        raise ForbiddenException(
            "Vous n'etes pas autorise a effectuer cette action sur le ticket.",
            error_code=ErrorCode.FORBIDDEN,
        )


def assert_transition_allowed(
    current_status: str | None,
    target_status: str,
    *,
    actor_role: str | None = None,
    allow_bypass: bool = False,
) -> None:
    role = normalize_role(actor_role)
    if allow_bypass and role in BYPASS_TRANSITION_ROLES:
        return

    current = normalize_status(current_status)
    target = normalize_status(target_status)
    allowed_sources = ALLOWED_TRANSITIONS.get(target)
    if not allowed_sources or current not in allowed_sources:
        raise BusinessException(
            f"Transition invalide : {current!r} -> {target!r}.",
            error_code=ErrorCode.INVALID_STATUS_TRANSITION,
        )


def assert_ticket_scope(
    actor: Any,
    request: Any,
    *,
    action: str | None = None,
    allowed_dir_unity_ids: set[int] | None = None,
) -> None:
    role = normalize_role(_value(actor, "role"))
    raw_role = str(_value(actor, "role") or "").strip().lower()
    actor_id = _value(actor, "id")
    actor_unity_id = _value(actor, "unity_id")
    request_unity_id = _value(request, "unity_id")
    request_direction_id = _value(request, "direction_id")
    request_assignee_id = _value(request, "assignee_id")
    request_requester_id = _value(request, "requester_id")

    if action == "request_reopen":
        if str(request_requester_id) == str(actor_id):
            return
        raise ForbiddenException(
            "Acces refuse : seul le demandeur peut demander la reouverture.",
            error_code=ErrorCode.FORBIDDEN,
        )

    if (
        action is not None
        and actor_id is not None
        and request_requester_id is not None
        and str(request_requester_id) == str(actor_id)
        and action not in OWN_REQUEST_ALLOWED_ACTIONS
    ):
        raise ForbiddenException(
            "Conflit d'interet : vous ne pouvez pas traiter votre propre demande.",
            error_code=ErrorCode.FORBIDDEN,
        )

    if role in GLOBAL_SCOPE_ROLES:
        return

    if action in {"close", "cancel"}:
        if str(request_requester_id) == str(actor_id):
            return

    if role == "user":
        if str(request_requester_id) == str(actor_id):
            return
        raise ForbiddenException(
            "Acces refuse : vous ne pouvez agir que sur vos propres demandes.",
            error_code=ErrorCode.FORBIDDEN,
        )

    if (
        action in TRIAGE_SCOPE_ACTIONS
        and _value(request, "in_triage") is True
        and role in QUEUE_HANDLER_ROLES
        and raw_role not in QUEUE_HANDLER_DENY_RAW_ROLES
    ):
        return

    if role in {"agent-support", "chief-service", "chief-departement"}:
        if request_assignee_id is not None and str(request_assignee_id) == str(actor_id):
            return
        allowed_ids = set(allowed_dir_unity_ids or set())
        if actor_unity_id is not None:
            allowed_ids.add(int(actor_unity_id))
        request_ids = {int(request_unity_id)} if request_unity_id is not None else set()
        if allowed_ids and request_ids.intersection(allowed_ids):
            return
        if actor_unity_id is not None and request_unity_id is not None:
            if str(request_unity_id) == str(actor_unity_id):
                return
        raise ForbiddenException(
            "Acces refuse : cette demande n'est pas dans votre perimetre.",
            error_code=ErrorCode.FORBIDDEN,
        )

    if role == "director":
        allowed_ids = set(allowed_dir_unity_ids or set())
        if actor_unity_id is not None:
            allowed_ids.add(int(actor_unity_id))
        request_ids = {
            int(v) for v in (request_unity_id, request_direction_id) if v is not None
        }
        if allowed_ids and request_ids.intersection(allowed_ids):
            return
        raise ForbiddenException(
            "Acces refuse : cette demande n'est pas dans votre direction.",
            error_code=ErrorCode.FORBIDDEN,
        )

    raise ForbiddenException(
        "Acces refuse : votre role ne permet pas d'agir sur cette demande.",
        error_code=ErrorCode.FORBIDDEN,
    )


def assert_qualify_target_allowed(
    actor_role: str | None,
    actor_id: str | int | None,
    assignee_id: str | int | None,
) -> None:
    """Compatibilite API : la qualification vers un assignee est autorisee pour
    tous les roles operationnels. La validation du role cible et du perimetre se
    fait dans le service, ou le compte destinataire est disponible.
    """
    return


def assert_assignment_allowed(
    actor: Any,
    request: Any,
    assignee_id: str | int,
    *,
    target_unity_id: str | int | None = None,
    target_role: str | None = None,
    allowed_scope_unity_ids: set[int] | None = None,
) -> None:
    """
    Regle metier assignation collaborative :
      - tous les roles operationnels peuvent devenir intervenant courant ;
      - admin garde un perimetre global ;
      - les autres roles assignent uniquement dans leur perimetre organisationnel.
    """
    role = normalize_role(_value(actor, "role"))
    raw_role = str(_value(actor, "role") or "").strip().lower()
    actor_id = _value(actor, "id")
    actor_unity_id = _value(actor, "unity_id")
    request_unity_id = _value(request, "unity_id")
    target_role_name = normalize_role(target_role)

    if target_role is None and str(assignee_id) == str(actor_id):
        target_role_name = role
        target_unity_id = actor_unity_id

    if raw_role in QUEUE_HANDLER_DENY_RAW_ROLES or role not in QUEUE_HANDLER_ROLES:
        raise ForbiddenException(
            "Votre role ne permet pas d'assigner un ticket.",
            error_code=ErrorCode.FORBIDDEN,
        )

    if target_role_name not in QUEUE_HANDLER_ROLES:
        raise ForbiddenException(
            "Le destinataire doit etre un role operationnel habilite au traitement.",
            error_code=ErrorCode.FORBIDDEN,
        )

    if role == "admin":
        return

    if target_role_name == "admin":
        raise ForbiddenException(
            "Seul un administrateur peut assigner un ticket a un administrateur.",
            error_code=ErrorCode.FORBIDDEN,
        )

    scope_ids: set[str] = {str(v) for v in (allowed_scope_unity_ids or set())}
    if actor_unity_id is not None:
        scope_ids.add(str(actor_unity_id))

    if target_unity_id is not None and scope_ids and str(target_unity_id) not in scope_ids:
        raise ForbiddenException(
            "Le destinataire n'appartient pas a votre perimetre operationnel.",
            error_code=ErrorCode.FORBIDDEN,
        )
    if request_unity_id is not None and scope_ids and str(request_unity_id) not in scope_ids:
        raise ForbiddenException(
            "Ce ticket n'appartient pas a votre perimetre operationnel.",
            error_code=ErrorCode.FORBIDDEN,
        )


def assert_service_reassignment_allowed(
    actor: Any,
    request: Any,
    target_unity_id: str | int,
    *,
    target_direction_id: str | int | None = None,
    actor_direction_id: str | int | None = None,
    reason: str | None = None,
) -> None:
    """
    Regle metier transfert service :
      - chief-departement : transfert uniquement dans la direction du ticket (Lot 2.5 —
        chief-service n'a plus acces a cette action, cf. ACTION_ALLOWED_ROLES["reassign"]).
      - director : transfert uniquement dans sa direction.
      - admin : transfert global.
    """
    role = normalize_role(_value(actor, "role"))
    actor_unity_id = _value(actor, "unity_id")
    request_direction_id = _value(request, "direction_id")

    if role in GLOBAL_SCOPE_ROLES:
        return

    if role == "chief-departement":
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise BusinessException(
                "Un motif est obligatoire pour reaffecter un ticket.",
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            )
        source_direction_id = request_direction_id or actor_direction_id
        if source_direction_id is None or target_direction_id is None:
            raise ForbiddenException(
                "Direction source ou cible introuvable pour ce transfert.",
                error_code=ErrorCode.FORBIDDEN,
            )
        if str(source_direction_id) != str(target_direction_id):
            raise ForbiddenException(
                "Un chef ne peut transferer un ticket que dans sa direction.",
                error_code=ErrorCode.FORBIDDEN,
            )
        return

    if role == "director":
        if actor_unity_id is None:
            raise ForbiddenException(
                "Compte non rattache a une direction.",
                error_code=ErrorCode.FORBIDDEN,
            )
        if target_direction_id is not None and str(target_direction_id) == str(actor_unity_id):
            return
        if str(target_unity_id) == str(actor_unity_id):
            return
        raise ForbiddenException(
            "Un directeur ne peut transferer un ticket que dans sa direction.",
            error_code=ErrorCode.FORBIDDEN,
        )

    raise ForbiddenException(
        "Votre role ne permet pas de transferer un ticket.",
        error_code=ErrorCode.FORBIDDEN,
    )


def assert_exceptional_escalation_reason(reason: str | None) -> None:
    """Lot 3.3 : motif obligatoire pour l'escalade exceptionnelle "Escalader au
    Directeur" — meme mecanique que assert_exceptional_resolve_reason."""
    clean_reason = reason.strip() if isinstance(reason, str) else ""
    if not clean_reason:
        raise BusinessException(
            "Un motif est obligatoire pour une escalade exceptionnelle au directeur.",
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
        )


def assert_escalation_allowed(actor: Any, request: Any) -> None:
    """
    Regle metier escalade :
      - agent-support : seulement un ticket qui lui est assigne.
      - chief/director/admin : escalade autorisee dans leur perimetre.
    """
    role = normalize_role(_value(actor, "role"))
    actor_id = _value(actor, "id")
    current_assignee_id = _value(request, "assignee_id")

    if role == "agent-support" and str(current_assignee_id) != str(actor_id):
        raise ForbiddenException(
            "Un agent peut escalader seulement un ticket qui lui est assigne.",
            error_code=ErrorCode.FORBIDDEN,
        )


def assert_role_specific_action_constraints(actor: Any, request: Any, action: str) -> None:
    """Point d'extension pour des contraintes propres à un rôle sur une action donnée.

    BR-TRANSMIT-001 (2026-08) : l'ancienne contrainte "un directeur ne peut résoudre
    qu'un ticket déjà escaladé" a été retirée — un directeur peut désormais terminer
    le traitement de tout ticket dont il est l'intervenant actuel (voir
    assert_is_current_handler), y compris reçu par transmission sans escalade
    préalable. Aucune contrainte spécifique n'est actuellement nécessaire ici.
    """
    return


def assert_ticket_action(
    actor: Any,
    request: Any,
    action: str,
    *,
    target_status: str | None = None,
    allowed_dir_unity_ids: set[int] | None = None,
) -> None:
    actor_role = _value(actor, "role")
    assert_action_allowed(actor_role, action)
    assert_ticket_scope(
        actor,
        request,
        action=action,
        allowed_dir_unity_ids=allowed_dir_unity_ids,
    )
    assert_role_specific_action_constraints(actor, request, action)
    if target_status is not None:
        assert_transition_allowed(
            _value(request, "request_status"),
            target_status,
            actor_role=actor_role,
        )


def assert_is_current_handler(
    actor: Any,
    request: Any,
    *,
    allowed_statuses: frozenset[str] = COLLABORATIVE_STATUSES,
) -> None:
    """
    BR-TRANSMIT-001 — garde générique du workflow collaboratif dynamique
    (transmission / terminaison de traitement).

    La règle principale n'est plus le rôle seul mais : l'acteur est-il
    l'intervenant actuel du ticket (request.assignee_id == actor.id) ? Le rôle ne
    sert que de filtre de sécurité général (uniquement les rôles traitants).

    admin : bypass volontaire, cohérent avec GLOBAL_SCOPE_ROLES ailleurs dans ce
    module — reste une intervention exceptionnelle, tracée via actor_role="admin"
    dans l'audit (workflow_detail.infos), jamais un traitement normal.
    """
    role = normalize_role(_value(actor, "role"))
    if role in GLOBAL_SCOPE_ROLES:
        return

    if role not in TREATING_ROLES:
        raise ForbiddenException(
            "Seuls les rôles de traitement (agent support, chef de service, chef de "
            "département, directeur) peuvent transmettre ou terminer un traitement.",
            error_code=ErrorCode.FORBIDDEN,
        )

    actor_id = _value(actor, "id")
    assignee_id = _value(request, "assignee_id")
    if assignee_id is None or actor_id is None or str(assignee_id) != str(actor_id):
        raise ForbiddenException(
            "Vous n'êtes plus l'intervenant actuel de ce ticket.",
            error_code=ErrorCode.FORBIDDEN,
        )

    current_status = normalize_status(_value(request, "request_status"))
    if current_status not in allowed_statuses:
        raise BusinessException(
            f"Impossible d'effectuer cette action : le ticket est actuellement {current_status!r}.",
            error_code=ErrorCode.INVALID_STATUS_TRANSITION,
        )
