/**
 * Carte d'invalidation TanStack Query par type d'événement SSE.
 *
 * Règles de nommage :
 *  ["request"]        → préfixe singulier : couvre ["request", id], ["request", id, "workflows"], ["request", id, "tasks"]
 *  ["requests"]       → liste paginée /requests/
 *  ["queue"]          → file d'attente (queue + my-tickets utilisent fetchQueue)
 *  ["my-tickets"]     → liste mes tickets (/app/my-tickets)
 *  ["my-tickets-stats"]→ stats KPI my-tickets
 *  ["my-stats"]       → stats personnelles agent (/stats/my)
 *  ["workflow"]       → préfixe : couvre ["workflow", id, "details"]
 *  ["sla-center"]     → centre SLA
 */

export type QueryKeyPrefix = readonly unknown[];

export const INVALIDATION_MAP: Record<string, QueryKeyPrefix[]> = {
  // ── Demandes ────────────────────────────────────────────────────────────────
  "request.created": [
    ["request"],          // détail + sous-queries
    ["requests"],         // liste
    ["queue"],            // file d'attente
    ["my-tickets"],       // mes tickets
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["triage"],
    ["sla-center"],
  ],
  "request.updated": [
    ["request"],
    ["requests"],
    ["queue"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["sla-center"],
  ],
  "request.status_changed": [
    ["request"],
    ["requests"],
    ["queue"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["my-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["triage"],
    ["sla-center"],
  ],
  "request.assigned": [
    ["request"],
    ["requests"],
    ["queue"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["my-stats"],
    ["stats"],
  ],
  "request.closed": [
    ["request"],
    ["requests"],
    ["queue"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["my-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["csat-stats"],
    ["sla-center"],
  ],
  "request.resolved": [
    ["request"],
    ["requests"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["my-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["csat-stats"],
    ["sla-center"],
  ],
  "request.reopened": [
    ["request"],
    ["requests"],
    ["queue"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["sla-center"],
  ],
  "request.cancelled": [
    ["request"],
    ["requests"],
    ["queue"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
  ],
  "request.deleted": [
    ["request"],
    ["requests"],
    ["queue"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["triage"],
    ["sla-center"],
  ],

  // ── Escalades ───────────────────────────────────────────────────────────────
  "escalation.created": [
    ["escalations"],
    ["request"],
    ["requests"],
    ["my-tickets"],
    ["stats"],
  ],
  "escalation.updated": [
    ["escalations"],
    ["request"],
    ["stats"],
  ],
  "escalation.reviewed": [
    ["escalations"],
    ["request"],
    ["stats"],
  ],
  "escalation.resolved": [
    ["escalations"],
    ["request"],
    ["requests"],
    ["my-tickets"],
    ["my-tickets-stats"],
    ["stats"],
  ],

  // ── Tâches ──────────────────────────────────────────────────────────────────
  "task.created": [
    ["tasks"],
    ["request"],
    ["requests"],
  ],
  "task.updated": [
    ["tasks"],
    ["request"],
  ],
  "task.completed": [
    ["tasks"],
    ["request"],
    ["requests"],
    ["my-tickets"],
    ["stats"],
  ],
  "task.approved": [
    ["tasks"],
    ["request"],
    ["requests"],
  ],
  "task.rejected": [
    ["tasks"],
    ["request"],
    ["requests"],
  ],
  "task.cancelled": [
    ["tasks"],
    ["request"],
    ["requests"],
  ],

  // ── Notifications ────────────────────────────────────────────────────────────
  "notification.created": [
    ["notifications"],
  ],
  "notification.read": [
    ["notifications"],
  ],

  // ── Annonces ─────────────────────────────────────────────────────────────────
  "announcement.created": [
    ["announcements"],
    ["announcements-active"],
    ["active-alerts"],
  ],
  "announcement.updated": [
    ["announcements"],
    ["announcements-active"],
    ["active-alerts"],
  ],
  "announcement.published": [
    ["announcements"],
    ["announcements-active"],
    ["active-alerts"],
  ],
  "announcement.closed": [
    ["announcements"],
    ["announcements-active"],
    ["active-alerts"],
  ],
  "announcement.deleted": [
    ["announcements"],
    ["announcements-active"],
    ["active-alerts"],
  ],

  // ── Utilisateurs ─────────────────────────────────────────────────────────────
  "user.created": [["users"]],
  "user.updated": [["users"]],
  "user.deleted": [["users"]],

  // ── Référentiels ─────────────────────────────────────────────────────────────
  "reference.updated": [["references"]],

  // ── Workflows ────────────────────────────────────────────────────────────────
  "workflow.updated": [
    ["workflow"],         // couvre ["workflow", id, "details"]
    ["workflows"],
    ["request"],          // couvre ["request", id, "workflows"]
    ["requests"],
  ],

  // ── Statistiques ─────────────────────────────────────────────────────────────
  "stats.updated": [
    ["stats"],
    ["dashboard-stats"],
    ["csat-stats"],
    ["my-stats"],
    ["my-tickets-stats"],
  ],
};
