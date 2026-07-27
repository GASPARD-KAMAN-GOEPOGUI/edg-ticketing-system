/**
 * RBAC — Rôles et permissions côté frontend.
 *
 * Miroir exact de backend/api/core/rbac.py.
 * Utilisé pour masquer/afficher les éléments UI selon le rôle de l'utilisateur.
 *
 * NOTE : cette vérification est côté UX uniquement.
 * La vraie sécurité est appliquée par le backend (401/403).
 */
import { useRole } from "./session";
import type { Role } from "./mock-data";

// ── Permissions ───────────────────────────────────────────────────────────────

export type Permission =
  // Profil
  | "view_own_profile"
  | "edit_own_profile"
  // Demandes
  | "create_request"
  | "view_own_requests"
  | "view_all_requests"
  | "assign_request"
  | "close_request"
  | "reopen_request"
  | "cancel_request"
  | "manage_requests"
  // Escalades
  | "escalate_request"
  | "manage_escalations"
  // Utilisateurs
  | "view_users"
  | "manage_users"
  // Rapports
  | "view_reports"
  | "view_global_reports"
  | "view_stats"
  // Référentiels
  | "view_references"
  | "manage_references"
  // Configuration
  | "manage_config"
  | "manage_sla"
  | "manage_routing"
  | "manage_homepage"
  // Journaux
  | "view_logs"
  // Base de connaissance
  | "view_knowledge"
  | "manage_knowledge"
  // Annonces
  | "view_announcements"
  | "manage_announcements"
  | "manage_communication"
  // Workflows & tâches
  | "view_workflows"
  | "manage_workflows"
  | "view_tasks"
  | "manage_tasks"
  // Divers
  | "view_notifications"
  | "view_sms_logs";

// ── Matrice Rôle → Permissions ────────────────────────────────────────────────

const _PUBLIC: Permission[] = [
  "view_knowledge",
  "view_announcements",
];

const _USER: Permission[] = [
  ..._PUBLIC,
  "view_own_profile",
  "edit_own_profile",
  "create_request",
  "view_own_requests",
  "cancel_request",
  "view_notifications",
];

const _AGENT: Permission[] = [
  ..._USER,
  "view_all_requests",
  "assign_request",
  "close_request",
  "reopen_request",
  "escalate_request",
  "view_workflows",
  "view_tasks",
  "manage_tasks",
  "manage_knowledge",
  "view_users",
  "view_references",
];

const _CHIEF: Permission[] = [
  ..._AGENT,
  "manage_requests",
  "manage_escalations",
  "view_reports",
  "view_stats",
  "manage_workflows",
];

const _DIRECTOR: Permission[] = [
  ..._CHIEF,
  "view_global_reports",
];

const _ADMIN: Permission[] = [
  // Toutes les permissions
  "view_own_profile", "edit_own_profile",
  "create_request", "view_own_requests", "view_all_requests",
  "assign_request", "close_request", "reopen_request", "cancel_request", "manage_requests",
  "escalate_request", "manage_escalations",
  "view_users", "manage_users",
  "view_reports", "view_global_reports", "view_stats",
  "view_references", "manage_references",
  "manage_config", "manage_sla", "manage_routing", "manage_homepage",
  "view_logs",
  "view_knowledge", "manage_knowledge",
  "view_announcements", "manage_announcements", "manage_communication",
  "view_workflows", "manage_workflows",
  "view_tasks", "manage_tasks",
  "view_notifications",
  "view_sms_logs",
];

export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  public:              _PUBLIC,
  user:                _USER,
  "agent-support":     _AGENT,
  "chief-service":     _CHIEF,
  "chief-departement": _CHIEF,
  director:            _DIRECTOR,
  admin:               _ADMIN,
};

// ── Hiérarchie ────────────────────────────────────────────────────────────────

const ROLE_HIERARCHY: Record<Role, number> = {
  public:              0,
  user:                1,
  "agent-support":     2,
  "chief-service":     3,
  "chief-departement": 3,
  director:            4,
  admin:               5,
};

// ── Fonctions utilitaires ─────────────────────────────────────────────────────

export function getRolePermissions(role: Role): Permission[] {
  return ROLE_PERMISSIONS[role] ?? [];
}

export function hasPermission(role: Role, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false;
}

export function hasAnyPermission(role: Role, permissions: Permission[]): boolean {
  return permissions.some((p) => hasPermission(role, p));
}

export function hasAllPermissions(role: Role, permissions: Permission[]): boolean {
  return permissions.every((p) => hasPermission(role, p));
}

export function isRoleAtLeast(currentRole: Role, minRole: Role): boolean {
  return (ROLE_HIERARCHY[currentRole] ?? -1) >= (ROLE_HIERARCHY[minRole] ?? 99);
}

// ── Hooks React ───────────────────────────────────────────────────────────────

/** Retourne la liste des permissions du rôle courant. */
export function usePermissions(): Permission[] {
  const [role] = useRole();
  return ROLE_PERMISSIONS[role] ?? [];
}

/** Retourne true si l'utilisateur courant dispose de la permission. */
export function useHasPermission(permission: Permission): boolean {
  const [role] = useRole();
  return hasPermission(role, permission);
}

/** Retourne true si l'utilisateur courant dispose d'au moins une des permissions. */
export function useHasAnyPermission(permissions: Permission[]): boolean {
  const [role] = useRole();
  return hasAnyPermission(role, permissions);
}

/** Retourne true si l'utilisateur courant a l'un des rôles listés. */
export function useHasRole(...roles: Role[]): boolean {
  const [role] = useRole();
  return roles.includes(role);
}

/** Retourne true si le rôle courant est au moins aussi élevé que minRole. */
export function useIsRoleAtLeast(minRole: Role): boolean {
  const [role] = useRole();
  return isRoleAtLeast(role, minRole);
}

/** Guard component — affiche children seulement si la permission est accordée. */
export function PermissionGuard({
  permission,
  children,
  fallback = null,
}: {
  permission: Permission;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}): React.ReactElement | null {
  const can = useHasPermission(permission);
  return (can ? children : fallback) as React.ReactElement | null;
}

/** Guard component — affiche children seulement si le rôle est accordé. */
export function RoleGuard({
  roles,
  children,
  fallback = null,
}: {
  roles: Role[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}): React.ReactElement | null {
  const [role] = useRole();
  return (roles.includes(role) ? children : fallback) as React.ReactElement | null;
}
