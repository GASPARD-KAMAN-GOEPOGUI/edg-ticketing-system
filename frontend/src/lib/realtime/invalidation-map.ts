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

/** Toutes les listes de tickets de l'application.
 *
 *  ⚠️ AJOUTER ICI toute nouvelle liste de tickets. C'est l'omission de cette
 *  étape qui avait rendu sept écrans muets au temps réel jusqu'au 2026-09-28.
 *  Une clé listée mais absente de l'écran courant ne coûte rien ; une clé
 *  oubliée se voit tout de suite — l'écran n'affiche plus la réalité. */
const TICKET_LISTS: QueryKeyPrefix[] = [
  ["request"],              // préfixe : couvre ["request", id, …]
  ["requests"],             // liste paginée /requests/
  ["queue"],                // plomberie partagée (tableaux de bord)
  ["qualify"],              // File d'attente — lit fetchTriage, PAS ["queue"]
  ["triage"],
  ["my-tickets"],           // Ma boîte de traitement
  ["transmitted-by-me"],    // Tickets transmis
  ["resolved-by-me"],       // Tickets résolus
  ["distribution"],         // Distribution du chef de division
  ["pv-tracking"],          // Suivi des interventions
  ["requests-history"],     // Historique
  ["tickets-supervision"],  // Supervision
];

/** Compteurs, badges et statistiques dérivés des tickets : ils vieillissent
 *  exactement au même rythme que les listes ci-dessus. */
const TICKET_COUNTERS: QueryKeyPrefix[] = [
  ["my-tickets-stats"],
  ["my-tickets-transmitted-count"],
  ["my-tickets-retransmitted-count"],
  ["my-stats"],
  ["stats"],
  ["dashboard-stats"],
  ["sla-center"],
];

const TICKET_TOUCHED: QueryKeyPrefix[] = [...TICKET_LISTS, ...TICKET_COUNTERS];

export const INVALIDATION_MAP: Record<string, QueryKeyPrefix[]> = {
  // ── Demandes ────────────────────────────────────────────────────────────────
  // TOUT evenement `request.*` perime TOUTES les listes de tickets. Le reglage
  // fin par evenement, en vigueur jusqu'au 2026-09-28, avait produit exactement
  // ce qu'il promettait d'eviter : sept ecrans ajoutes au fil du temps
  // (`qualify`, `transmitted-by-me`, `distribution`, `resolved-by-me`,
  // `pv-tracking` et les deux compteurs) n'etaient rattaches a AUCUN evenement,
  // et ne se rafraichissaient donc jamais en temps reel.
  //
  // Sur-invalider ne coute rien : React Query ne refetch que les requetes
  // MONTEES. Invalider une cle absente de l'ecran courant est sans effet — a
  // l'inverse, en oublier une se paie par un ecran qui ment a l'utilisateur.
  "request.created": TICKET_TOUCHED,
  "request.updated": TICKET_TOUCHED,
  "request.status_changed": TICKET_TOUCHED,
  "request.assigned": TICKET_TOUCHED,
  "request.closed": TICKET_TOUCHED,
  "request.resolved": TICKET_TOUCHED,
  "request.reopened": TICKET_TOUCHED,
  "request.cancelled": TICKET_TOUCHED,
  "request.deleted": TICKET_TOUCHED,
  "request.routed": TICKET_TOUCHED,
  "request.reassigned": TICKET_TOUCHED,
  "request.transmitted": TICKET_TOUCHED,
  "request.transferred_direction": TICKET_TOUCHED,
  "request.priority_changed": TICKET_TOUCHED,
  "request.field_checked": TICKET_TOUCHED,
  "request.rejected": TICKET_TOUCHED,
  "request.reopen_requested": TICKET_TOUCHED,
  "request.reopen_rejected": TICKET_TOUCHED,
  "request.distributed": TICKET_TOUCHED,
  "request.pv_submitted": TICKET_TOUCHED,
  "request.pv_archived": TICKET_TOUCHED,

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
