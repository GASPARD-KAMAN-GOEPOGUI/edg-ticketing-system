"""
RBAC — Rôles et permissions EDG Support.

Hiérarchie des rôles (du moins au plus privilégié) :
  public < user < chief-service/technicien/chef-division-support < admin

Chaque rôle hérite des permissions des rôles inférieurs.
Les permissions sont cumulatives : un chief a toutes les permissions d'un agent.

Usage dans les routes :
    from api.dependencies import require_roles, require_permissions

    @router.get("/...", dependencies=[Depends(require_roles("admin"))])
    @router.get("/...", dependencies=[Depends(require_permissions("manage_users"))])
"""
from __future__ import annotations

from enum import Enum


# ── Permissions ───────────────────────────────────────────────────────────────

class Permission(str, Enum):
    # Profil
    VIEW_OWN_PROFILE        = "view_own_profile"
    EDIT_OWN_PROFILE        = "edit_own_profile"

    # Demandes
    CREATE_REQUEST          = "create_request"
    VIEW_OWN_REQUESTS       = "view_own_requests"
    VIEW_ALL_REQUESTS       = "view_all_requests"
    ASSIGN_REQUEST          = "assign_request"
    CLOSE_REQUEST           = "close_request"
    REOPEN_REQUEST          = "reopen_request"
    CANCEL_REQUEST          = "cancel_request"
    MANAGE_REQUESTS         = "manage_requests"

    # Escalades
    ESCALATE_REQUEST        = "escalate_request"
    MANAGE_ESCALATIONS      = "manage_escalations"

    # Utilisateurs / comptes
    VIEW_USERS              = "view_users"
    MANAGE_USERS            = "manage_users"

    # Rapports & stats
    VIEW_REPORTS            = "view_reports"
    VIEW_GLOBAL_REPORTS     = "view_global_reports"
    VIEW_STATS              = "view_stats"

    # Référentiels (tables de référence)
    VIEW_REFERENCES         = "view_references"
    MANAGE_REFERENCES       = "manage_references"

    # Configuration
    MANAGE_CONFIG           = "manage_config"
    MANAGE_SLA              = "manage_sla"
    MANAGE_ROUTING          = "manage_routing"
    MANAGE_HOMEPAGE         = "manage_homepage"

    # Journaux
    VIEW_LOGS               = "view_logs"

    # Workflows & tâches
    VIEW_WORKFLOWS          = "view_workflows"
    MANAGE_WORKFLOWS        = "manage_workflows"
    VIEW_TASKS              = "view_tasks"
    MANAGE_TASKS            = "manage_tasks"

    # Notifications
    VIEW_NOTIFICATIONS      = "view_notifications"

    # SMS logs
    VIEW_SMS_LOGS           = "view_sms_logs"


# ── Matrice Rôle → Permissions ────────────────────────────────────────────────

_P = Permission

_USER: set[Permission] = {
    _P.VIEW_OWN_PROFILE,
    _P.EDIT_OWN_PROFILE,
    _P.CREATE_REQUEST,
    _P.VIEW_OWN_REQUESTS,
    _P.CANCEL_REQUEST,
    _P.VIEW_NOTIFICATIONS,
}

_AGENT: set[Permission] = _USER | {
    _P.VIEW_ALL_REQUESTS,
    _P.ASSIGN_REQUEST,
    _P.CLOSE_REQUEST,
    _P.REOPEN_REQUEST,
    _P.ESCALATE_REQUEST,
    _P.VIEW_WORKFLOWS,
    _P.VIEW_TASKS,
    _P.MANAGE_TASKS,
    _P.VIEW_USERS,
    _P.VIEW_REFERENCES,
}

_ADMIN: set[Permission] = {p for p in _P}  # toutes les permissions

# `dg`, `chief`, `chief-department(ement)` et `chief-dept` ont ete retires le
# 2026-09-25 avec les roles `director` et `chief-departement` : un alias qui
# resout vers un role inexistant ferait silencieusement refuser l'acces.
LEGACY_ROLE_ALIASES: dict[str, str] = {
    "agent": "chief-service",
}

ROLE_GROUP_ALIASES: dict[str, set[str]] = {
    "agent": {"chief-service", "technicien", "chef-division-support"},
    "chief-service": {"chief-service", "technicien", "chef-division-support"},
    "technicien": {"chief-service", "technicien", "chef-division-support"},
    "chef-division-support": {"chief-service", "technicien", "chef-division-support"},
}


def normalize_role(role: str | None) -> str:
    """Normalise les anciens libelles de role vers la nomenclature CDC."""
    value = (role or "user").strip().lower()
    return LEGACY_ROLE_ALIASES.get(value, value)


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    # Le rôle public n'a aucune permission applicative : ses deux seules
    # (view_knowledge, view_announcements) sont parties avec la base de
    # connaissances et les annonces le 2026-09-24.
    "public":           set(),
    "user":             _USER,
    "chief-service":    _AGENT,
    "technicien":       _AGENT,
    "chef-division-support": _AGENT,
    "admin":            _ADMIN,
}

# Hiérarchie pour les comparaisons
ROLE_HIERARCHY: dict[str, int] = {
    "public":           0,
    "user":             1,
    "chief-service":    2,
    "technicien":       2,
    "chef-division-support": 2,
    "admin":            5,
}


def has_permission(role: str, permission: Permission) -> bool:
    """Vérifie si un rôle dispose d'une permission donnée."""
    return permission in ROLE_PERMISSIONS.get(normalize_role(role), set())


def _expand_required_roles(*required_roles: str) -> set[str]:
    expanded: set[str] = set()
    for role in required_roles:
        if role is None:
            continue
        raw = role.strip().lower()
        expanded.update(ROLE_GROUP_ALIASES.get(raw, ROLE_GROUP_ALIASES.get(normalize_role(role), {normalize_role(role)})))
    return expanded


def has_role(current_role: str, *required_roles: str) -> bool:
    """Vérifie si le rôle actuel est dans la liste des rôles requis."""
    allowed = _expand_required_roles(*required_roles)
    return normalize_role(current_role) in allowed


def role_at_least(current_role: str, min_role: str) -> bool:
    """Vérifie si le rôle actuel est au moins aussi élevé que min_role."""
    return ROLE_HIERARCHY.get(normalize_role(current_role), -1) >= ROLE_HIERARCHY.get(normalize_role(min_role), 99)
