/**
 * Système de capacités hiérarchiques — Algo 2
 *
 * Les rôles sont additifs : un chief-service/chief-departement hérite des capacités agent-support,
 * qui hérite de toutes celles d'un user.
 * Règle : le rôle détermine ce qu'on peut FAIRE — la propriété du ticket
 * détermine ce qu'on VOIT (voir iAmRequester dans les composants).
 */
import type { RequestStatus, Role } from "@/lib/mock-data";

// ── Rang hiérarchique ─────────────────────────────────────────────────────────

const ROLE_RANK: Record<Role, number> = {
  public:              0,  // visiteur non-authentifié — aucune capacité opérationnelle
  user:                1,
  "agent-support":     2,
  "chief-service":     3,
  "chief-departement": 3,
  director:            4,
  admin:               5,
};

// ── Plancher de capacité (rang minimum requis) ────────────────────────────────

const CAPABILITY_FLOOR: Record<string, number> = {
  // Tout employé peut soumettre une demande pour lui-même
  submit_request:   1,
  // Agents et au-dessus traitent les tickets
  process_ticket:   2,
  // Chefs et au-dessus supervisent une équipe
  supervise_team:   3,
  // Directeurs et au-dessus voient leur direction
  view_direction:   4,
  // Admin uniquement pour le tableau global consolidé
  view_global:      5,
  // Admin uniquement pour le backoffice système
  admin_system:     5,
};

// ── Fonction principale ───────────────────────────────────────────────────────

/**
 * Retourne true si le rôle donné possède la capacité demandée.
 *
 * Usage :
 *   can(role, "submit_request")  → true pour TOUS les rôles
 *   can(role, "process_ticket")  → true pour agent-support, chief-service, chief-departement, director, admin
 *   can(role, "admin_system")    → true uniquement pour admin
 */
export function can(role: Role, capability: string): boolean {
  const rank = ROLE_RANK[role] ?? 0;
  const floor = CAPABILITY_FLOOR[capability] ?? 99;
  return rank >= floor;
}

/**
 * Retourne true si l'utilisateur est le demandeur du ticket.
 * À utiliser pour adapter la vue détail (Algo 1 — ownership-based perspective).
 *
 * Usage :
 *   const iAmRequester = isRequester(r.requesterId, sessionUser?.id);
 */
export function isRequester(
  ticketRequesterId: string | number | undefined | null,
  currentUserId: string | number | undefined | null,
): boolean {
  if (!ticketRequesterId || !currentUserId) return false;
  return String(ticketRequesterId) === String(currentUserId);
}

export type TicketAction =
  | "requester_edit"
  | "self_assign"
  | "request_info"
  | "resume"
  | "assign"
  | "resolve"
  | "transmit_treatment"
  | "close"
  | "reopen"
  | "cancel"
  | "reject"
  | "escalate"
  | "escalate_to_director"
  | "change_priority"
  | "change_service"
  | "transfer_direction"
  | "accept_workflow_step";

type TicketActionOptions = {
  isRequester?: boolean;
  isAssignedToMe?: boolean;
  hasAssignee?: boolean;
  canReopenClosed?: boolean;
};

const AUTHENTICATED_ROLES: Role[] = ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"];

const TICKET_ACTION_ROLES: Record<TicketAction, Role[]> = {
  requester_edit: AUTHENTICATED_ROLES,
  self_assign: ["agent-support"],
  request_info: ["agent-support", "chief-service", "chief-departement", "director", "admin"],
  resume: ["agent-support", "chief-service", "chief-departement", "director", "admin"],
  assign: ["agent-support", "chief-service", "chief-departement", "director", "admin"],
  // BR-TRANSMIT-001 (remplace Lot 3.2) : "Terminer le traitement" est réservé à
  // l'intervenant actuel (isAssignedToMe, voir canTicketAction ci-dessous) — chief-
  // departement redevient éligible dès lors qu'il est devenu intervenant actuel via
  // une transmission ; le rôle n'est plus qu'un filtre de sécurité général.
  resolve: ["agent-support", "chief-service", "chief-departement", "director", "admin"],
  // BR-TRANSMIT-001 : "Transmettre le traitement" — mêmes rôles traitants que resolve,
  // même garde isAssignedToMe.
  transmit_treatment: ["agent-support", "chief-service", "chief-departement", "director", "admin"],
  close: AUTHENTICATED_ROLES,
  // BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : réservé au demandeur
  // (garde réelle : options.isRequester dans canTicketAction ci-dessous) — le rôle
  // ne sert que de filtre de sécurité général, comme ailleurs dans ce module.
  reopen: AUTHENTICATED_ROLES,
  cancel: ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"],
  reject: ["chief-service", "chief-departement", "admin"],
  escalate: ["agent-support", "chief-service", "chief-departement", "director", "admin"],
  // Lot 3.3 : "Escalade exceptionnelle" — reservee au chef de departement.
  escalate_to_director: ["chief-departement"],
  change_priority: ["chief-service", "chief-departement", "director", "admin"],
  // Lot 2.5 : chief-service n'a plus accès à "Changer de service" (reste chief-departement,
  // director, admin) — cf. ticket_actions.ACTION_ALLOWED_ROLES["reassign"] côté backend.
  change_service: ["chief-departement", "director", "admin"],
  transfer_direction: ["director", "admin"],
  accept_workflow_step: ["agent-support", "chief-service", "chief-departement", "director", "admin"],
};

const TICKET_ACTION_STATUSES: Record<TicketAction, RequestStatus[]> = {
  requester_edit: ["new", "qualifying"],
  self_assign: ["new", "qualifying", "qualified", "reopened"],
  request_info: ["in_progress", "assigned"],
  resume: ["pending"],
  assign: ["new", "qualifying", "qualified", "reopened"],
  resolve: ["assigned", "in_progress", "pending", "escalated"],
  transmit_treatment: ["assigned", "in_progress", "pending", "escalated"],
  close: ["resolved"],
  reopen: ["resolved", "closed", "rejected"],
  cancel: ["new", "qualifying", "qualified", "assigned", "in_progress", "pending"],
  reject: ["new", "qualifying", "qualified", "assigned", "in_progress", "pending"],
  escalate: ["qualifying", "assigned", "in_progress", "pending"],
  escalate_to_director: ["qualifying", "assigned", "in_progress", "pending"],
  change_priority: ["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "escalated", "reopened"],
  change_service: ["new", "qualifying", "qualified", "reopened"],
  transfer_direction: ["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "escalated", "reopened"],
  accept_workflow_step: ["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "escalated", "reopened"],
};

const OWN_REQUEST_ALLOWED_ACTIONS = new Set<TicketAction>([
  "requester_edit",
  "close",
  "reopen",
  "cancel",
]);

export function canTicketAction(
  role: Role,
  action: TicketAction,
  status: RequestStatus | undefined | null,
  options: TicketActionOptions = {},
): boolean {
  if (!status) return false;
  if (!TICKET_ACTION_ROLES[action].includes(role)) return false;
  if (!TICKET_ACTION_STATUSES[action].includes(status)) return false;
  if (options.isRequester === true && !OWN_REQUEST_ALLOWED_ACTIONS.has(action)) return false;

  // BR-TRANSMIT-001 : "Terminer le traitement" et "Transmettre le traitement" sont
  // réservés à l'intervenant actuel — remplace l'ancienne restriction "director
  // uniquement si escaladé" (le rôle seul ne suffit plus, quel qu'il soit).
  if (action === "resolve" || action === "transmit_treatment") {
    return options.isAssignedToMe === true;
  }
  if (action === "requester_edit") return options.isRequester === true;
  if (action === "self_assign") return options.hasAssignee !== true;
  // BR-QUEUE-AUTO-START-001 — "take_ownership"/"Démarrer traitement" supprimé :
  // une prise/assignation depuis la File d'attente (self_assign/assign côté
  // backend) démarre désormais toujours directement `in_progress`, il n'existe
  // plus de second temps "assigned → Démarrer traitement" à exposer en capacité.
  // BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : réservé au demandeur,
  // aucune approbation hiérarchique distincte (approve_reopen/reject_reopen supprimés).
  if (action === "reopen") {
    if (options.isRequester !== true) return false;
    if (status === "closed" && options.canReopenClosed === false) return false;
  }

  return true;
}
