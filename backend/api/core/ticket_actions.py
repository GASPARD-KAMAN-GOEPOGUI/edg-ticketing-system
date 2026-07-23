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
STATUS_ALIASES = {
    "cancalled": "cancelled",
    "canceled": "cancelled",
    "escaladed": "escalated",
}
TERMINAL_STATUSES = frozenset({"cancelled", "closed", "resolved", "rejected"})
QUALIFIABLE_STATUSES = frozenset({"new", "qualifying", "qualified", "reopened"})

ACTION_ALLOWED_ROLES: dict[str, set[str]] = {
    "qualify": {"agent", "chief", "admin"},
    "assign": {"agent", "chief", "admin"},
    "resolve": {"agent", "chief", "director", "admin"},
    "close": {"user", "agent", "chief", "director", "admin"},
    "request_reopen": {"user", "agent", "chief", "director", "admin"},
    "reopen": {"chief", "director", "admin"},
    "reject_reopen": {"chief", "director", "admin"},
    "cancel": {"user", "agent", "chief", "director", "admin"},
    "reassign": {"chief", "director", "admin"},
    "transfer_direction": {"director", "admin"},
    "reject": {"chief", "admin"},
    "escalate": {"agent", "chief", "director", "admin"},
    "change_priority": {"chief", "director", "admin"},
}

TRIAGE_SCOPE_ACTIONS = frozenset({"qualify", "resolve"})


def normalize_status(status: str | None) -> str:
    clean = (status or "new").strip().lower()
    return STATUS_ALIASES.get(clean, clean)


def _value(obj: Any, name: str) -> Any:
    return getattr(obj, name, None)


def assert_action_allowed(actor_role: str | None, action: str) -> None:
    allowed = ACTION_ALLOWED_ROLES.get(action)
    role = normalize_role(actor_role)
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
        and role in {"agent", "chief"}
    ):
        return

    if role in {"agent", "chief"}:
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


def assert_assignment_allowed(
    actor: Any,
    request: Any,
    assignee_id: str | int,
    *,
    target_unity_id: str | int | None = None,
    target_role: str | None = None,
) -> None:
    """
    Regle metier assignation :
      - agent : auto-assignation uniquement, sur un ticket libre de son perimetre.
      - chief : assignation a un agent de sa propre unite.
      - admin : assignation globale.
    """
    role = normalize_role(_value(actor, "role"))
    actor_id = _value(actor, "id")
    actor_unity_id = _value(actor, "unity_id")
    current_assignee_id = _value(request, "assignee_id")
    request_unity_id = _value(request, "unity_id")
    target_role_name = normalize_role(target_role)

    if role == "agent":
        if str(assignee_id) != str(actor_id):
            raise ForbiddenException(
                "Un agent peut seulement s'auto-assigner un ticket.",
                error_code=ErrorCode.FORBIDDEN,
            )
        if current_assignee_id is not None and str(current_assignee_id) != str(actor_id):
            raise BusinessException(
                "Ce ticket est deja assigne a un autre agent.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        if (
            target_unity_id is not None
            and actor_unity_id is not None
            and str(target_unity_id) != str(actor_unity_id)
        ):
            raise ForbiddenException(
                "Un agent peut seulement s'auto-assigner un ticket de son unite.",
                error_code=ErrorCode.FORBIDDEN,
            )
        if current_assignee_id is not None:
            raise BusinessException(
                "Ce ticket vous est deja assigne.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        return

    if role == "chief":
        if target_role_name != "agent":
            raise ForbiddenException(
                "Un chef peut assigner uniquement un agent de son service.",
                error_code=ErrorCode.FORBIDDEN,
            )
        if (
            actor_unity_id is None
            or target_unity_id is None
            or str(target_unity_id) != str(actor_unity_id)
        ):
            raise ForbiddenException(
                "Un chef ne peut pas assigner un agent hors de son service.",
                error_code=ErrorCode.FORBIDDEN,
            )
        if (
            request_unity_id is not None
            and str(request_unity_id) != str(actor_unity_id)
        ):
            raise ForbiddenException(
                "Un chef ne peut assigner que les tickets de son service.",
                error_code=ErrorCode.FORBIDDEN,
            )
        return

    if role == "admin":
        return

    raise ForbiddenException(
        "Votre role ne permet pas d'assigner un ticket.",
        error_code=ErrorCode.FORBIDDEN,
    )


def assert_service_reassignment_allowed(
    actor: Any,
    request: Any,
    target_unity_id: str | int,
    *,
    target_direction_id: str | int | None = None,
    actor_direction_id: str | int | None = None,
) -> None:
    """
    Regle metier transfert service :
      - chief : transfert uniquement dans la direction du ticket.
      - director : transfert uniquement dans sa direction.
      - admin : transfert global.
    """
    role = normalize_role(_value(actor, "role"))
    actor_unity_id = _value(actor, "unity_id")
    request_direction_id = _value(request, "direction_id")

    if role in GLOBAL_SCOPE_ROLES:
        return

    if role == "chief":
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


def assert_escalation_allowed(actor: Any, request: Any) -> None:
    """
    Regle metier escalade :
      - agent : seulement un ticket qui lui est assigne.
      - chief/director/admin : escalade autorisee dans leur perimetre.
    """
    role = normalize_role(_value(actor, "role"))
    actor_id = _value(actor, "id")
    current_assignee_id = _value(request, "assignee_id")

    if role == "agent" and str(current_assignee_id) != str(actor_id):
        raise ForbiddenException(
            "Un agent peut escalader seulement un ticket qui lui est assigne.",
            error_code=ErrorCode.FORBIDDEN,
        )


def assert_role_specific_action_constraints(actor: Any, request: Any, action: str) -> None:
    role = normalize_role(_value(actor, "role"))
    current_status = normalize_status(_value(request, "request_status"))

    if role == "director" and action == "resolve" and current_status != "escalated":
        raise ForbiddenException(
            "Un directeur peut resoudre uniquement un ticket escalade ou en arbitrage.",
            error_code=ErrorCode.FORBIDDEN,
        )


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
