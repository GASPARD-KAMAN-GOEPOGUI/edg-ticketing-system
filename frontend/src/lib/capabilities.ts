/**
 * Système de capacités hiérarchiques — Algo 2
 *
 * Les rôles sont additifs : un chief hérite de toutes les capacités d'un agent,
 * qui hérite de toutes celles d'un user.
 * Règle : le rôle détermine ce qu'on peut FAIRE — la propriété du ticket
 * détermine ce qu'on VOIT (voir iAmRequester dans les composants).
 */
import type { Role } from "@/lib/mock-data";

// ── Rang hiérarchique ─────────────────────────────────────────────────────────

const ROLE_RANK: Record<Role, number> = {
  public:   0,  // visiteur non-authentifié — aucune capacité opérationnelle
  user:     1,
  agent:    2,
  chief:    3,
  director: 4,
  dg:       5,
  admin:    6,
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
  // DG et au-dessus voient le tableau global
  view_global:      5,
  // Admin uniquement pour le backoffice système
  admin_system:     6,
};

// ── Fonction principale ───────────────────────────────────────────────────────

/**
 * Retourne true si le rôle donné possède la capacité demandée.
 *
 * Usage :
 *   can(role, "submit_request")  → true pour TOUS les rôles
 *   can(role, "process_ticket")  → true pour agent, chief, director, dg, admin
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
