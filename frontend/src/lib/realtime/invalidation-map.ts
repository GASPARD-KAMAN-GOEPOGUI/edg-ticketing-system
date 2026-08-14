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
 *  ["requests-history"] → historique demandes clôturées/annulées/rejetées (/app/history)
 *  ["tickets-supervision"] / ["agents-supervision"] / ["chiefs-supervision"] → /app/supervision
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
    ["requests-history"],
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
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["sla-center"],
  ],
  "request.status_changed": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
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
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["my-stats"],
    ["stats"],
  ],
  "request.closed": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
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
    ["requests-history"],
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
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["sla-center"],
  ],
  "request.cancelled": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
  ],
  "request.deleted": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["triage"],
    ["sla-center"],
  ],
  "request.routed": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["stats"],
    ["triage"],
  ],
  "request.reassigned": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["my-stats"],
    ["stats"],
  ],
  // BR-TRANSMIT-001 — "Transmettre le traitement" : change assignee_id sans changer
  // de statut, même surface d'invalidation que request.assigned/reassigned.
  "request.transmitted": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["my-stats"],
    ["stats"],
  ],
  "request.transferred_direction": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["triage"],
  ],
  "request.priority_changed": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["stats"],
    ["dashboard-stats"],
    ["sla-center"],
  ],
  "request.rejected": [
    ["request"],
    ["requests"],
    ["queue"],
    ["tickets-supervision"],
    ["my-tickets"],
    ["requests-history"],
    ["my-tickets-stats"],
    ["stats"],
    ["dashboard-stats"],
    ["triage"],
  ],
  "request.reopen_requested": [
    ["request"],
    ["requests"],
    ["my-tickets"],
    ["requests-history"],
    ["queue"],
    ["tickets-supervision"],
  ],
  "request.reopen_rejected": [
    ["request"],
    ["requests"],
    ["my-tickets"],
    ["requests-history"],
  ],

  // ── Escalades ───────────────────────────────────────────────────────────────
  "escalation.created": [
    ["escalations"],
    ["request"],
    ["requests"],
    ["my-tickets"],
    ["requests-history"],
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
    ["requests-history"],
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
    ["requests-history"],
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
  "user.created": [["users"], ["agents-supervision"], ["chiefs-supervision"]],
  "user.updated": [["users"], ["agents-supervision"], ["chiefs-supervision"]],
  "user.deleted": [["users"], ["agents-supervision"], ["chiefs-supervision"]],

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
