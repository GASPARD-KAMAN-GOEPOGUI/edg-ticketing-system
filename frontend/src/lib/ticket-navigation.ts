import type { Role } from "@/lib/mock-data";

export type TicketDetailRoute =
  | "/app/requests/$id"
  | "/app/history/tickets/$id"
  | "/app/queue/tickets/$id"
  // Espaces encore atteignables depuis le tableau de bord, mais dont le menu
  // latéral est commenté : ils restent des destinations EXPLICITES (`detailTo`),
  // jamais un choix de `ticketMenuRoute` — y déposer quelqu'un depuis une
  // notification le laisserait sans menu de retour.
  | "/app/supervision/tickets/$id"
  | "/app/dg/tickets/$id"
  | "/app/sla-center/tickets/$id"
  | "/app/transmitted/tickets/$id"
  | "/app/my-tickets/tickets/$id"
  | "/app/distribution/tickets/$id"
  | "/app/resolved/tickets/$id"
  | "/app/admin/tickets/$id";

export type TicketListRoute =
  | "/app/requests"
  | "/app/history"
  | "/app/queue"
  | "/app/supervision"
  | "/app/dg"
  | "/app/sla-center"
  | "/app/transmitted"
  | "/app/my-tickets"
  | "/app/distribution"
  | "/app/resolved"
  | "/app/admin/users";

export function ticketDetailRouteForList(route: TicketListRoute): TicketDetailRoute {
  if (route === "/app/supervision") return "/app/supervision/tickets/$id";
  if (route === "/app/dg") return "/app/dg/tickets/$id";
  if (route === "/app/sla-center") return "/app/sla-center/tickets/$id";
  if (route === "/app/queue") return "/app/queue/tickets/$id";
  if (route === "/app/transmitted") return "/app/transmitted/tickets/$id";
  if (route === "/app/history") return "/app/history/tickets/$id";
  if (route === "/app/my-tickets") return "/app/my-tickets/tickets/$id";
  if (route === "/app/distribution") return "/app/distribution/tickets/$id";
  if (route === "/app/resolved") return "/app/resolved/tickets/$id";
  if (route === "/app/admin/users") return "/app/admin/tickets/$id";
  return "/app/requests/$id";
}

/** Destinations qu'une notification peut choisir : les espaces réellement
 *  présents dans la barre latérale. Supervision, DG et Centre SLA en sont
 *  exclus par construction (leurs menus sont commentés). */
export type NotificationDestination = Exclude<
  TicketDetailRoute,
  "/app/supervision/tickets/$id" | "/app/dg/tickets/$id" | "/app/sla-center/tickets/$id"
>;

/** Rôles dont la barre latérale comporte le menu, et dont la garde de route
 *  (`requireRole` dans chaque fichier `app.*_.tickets.$id.tsx`) laisse passer.
 *  Envoyer quelqu'un dans un espace absent de ses menus le dépose sans fil
 *  d'Ariane ni retour — ou, pire, le fait refuser par la garde. */
const MENU_ROLES: Record<NotificationDestination, readonly Role[]> = {
  "/app/requests/$id": ["user", "chief-service", "technicien", "chef-division-support", "admin"],
  "/app/history/tickets/$id": ["user", "chief-service", "technicien", "chef-division-support", "admin"],
  "/app/my-tickets/tickets/$id": ["chief-service", "technicien", "chef-division-support", "admin"],
  "/app/queue/tickets/$id": ["chief-service", "admin"],
  "/app/distribution/tickets/$id": ["chef-division-support"],
  "/app/transmitted/tickets/$id": ["chief-service", "technicien", "chef-division-support", "admin"],
  "/app/resolved/tickets/$id": ["chief-service", "technicien", "chef-division-support", "admin"],
  "/app/admin/tickets/$id": ["admin"],
};

function roleHasMenu(route: NotificationDestination, role?: Role): boolean {
  return !!role && MENU_ROLES[route].includes(role);
}

/** Événements du journal qui traduisent un dessaisissement : celui qui les a
 *  émis retrouve le ticket dans « Tickets transmis ». Même liste que
 *  `RepositoryRequest.list_transmitted_by_actor` (`_HANDOVER_EVENTS`), à
 *  laquelle s'ajoute `assigned` lorsque le destinataire diffère de l'émetteur
 *  (sinon c'est une auto-assignation, qui ne transmet rien). */
const HANDOVER_EVENTS = new Set([
  "treatment_transmitted",
  "distributed_to_division",
  "distribution_assigned",
]);

/** État du ticket nécessaire pour décider de son menu. Volontairement minimal :
 *  n'importe quelle source (fiche complète, entrée de liste) peut le fournir. */
export type TicketLocation = {
  status?: string;
  inTriage?: boolean;
  assigneeId?: string;
  requesterId?: string;
  distributorId?: string;
  timeline?: ReadonlyArray<{ type?: string; actorId?: string; targetUserId?: string }>;
};

function sameId(a?: string, b?: string): boolean {
  return !!a && !!b && String(a) === String(b);
}

function isHandoverActor(ticket: TicketLocation, meId?: string): boolean {
  if (!meId) return false;
  return (ticket.timeline ?? []).some((event) => {
    if (!sameId(event.actorId, meId)) return false;
    if (event.type && HANDOVER_EVENTS.has(event.type)) return true;
    // `assigned` sert aussi à « Prendre le ticket » : ne compte que si le
    // destinataire est quelqu'un d'autre.
    return event.type === "assigned"
      && !!event.targetUserId
      && !sameId(event.targetUserId, meId);
  });
}

/**
 * Menu dans lequel le ticket se trouve RÉELLEMENT pour cette personne, et donc
 * route de détail à ouvrir.
 *
 * Décidé à partir de l'état courant du ticket, jamais d'une URL figée à
 * l'émission d'une notification : entre l'envoi et le clic, le ticket a pu être
 * qualifié, imputé, transmis, résolu. L'ancienne logique suivait
 * `notification.action_url`, ce qui déposait l'utilisateur dans un espace ne
 * contenant plus le ticket.
 *
 * Ordre : le menu le plus actionnable gagne — ce que la personne a à faire
 * maintenant primant sur ce qu'elle a fait avant. Un ticket résolu passe donc
 * par « Tickets résolus » même si elle l'avait transmis.
 */
export function ticketMenuRoute(
  ticket: TicketLocation,
  role?: Role,
  meId?: string,
): NotificationDestination {
  const status = (ticket.status ?? "").trim().toLowerCase();

  // 1. File d'attente — reste à qualifier.
  if (ticket.inTriage && roleHasMenu("/app/queue/tickets/$id", role)) {
    return "/app/queue/tickets/$id";
  }

  // 2. Distribution — imputé à ce chef de division, pas encore assigné.
  if (sameId(ticket.distributorId, meId) && !ticket.assigneeId
      && roleHasMenu("/app/distribution/tickets/$id", role)) {
    return "/app/distribution/tickets/$id";
  }

  // 3. Ma boîte de traitement — j'en suis l'intervenant actuel. Passe avant
  //    « Tickets résolus » : le ticket est encore à moi, et c'est de là que je
  //    le clôture ou le reprends.
  if (sameId(ticket.assigneeId, meId) && !["resolved", "closed"].includes(status)
      && roleHasMenu("/app/my-tickets/tickets/$id", role)) {
    return "/app/my-tickets/tickets/$id";
  }

  // 4. Tickets résolus / Historique — selon que le traitement est fini ou le
  //    ticket clos. L'historique est le seul des deux ouvert au requérant.
  if (status === "resolved" && roleHasMenu("/app/resolved/tickets/$id", role)
      && (sameId(ticket.assigneeId, meId) || isHandoverActor(ticket, meId))) {
    return "/app/resolved/tickets/$id";
  }
  if (["closed", "cancelled", "rejected"].includes(status)
      && roleHasMenu("/app/history/tickets/$id", role)) {
    return "/app/history/tickets/$id";
  }

  // 5. Tickets transmis — je m'en suis dessaisi, je le suis de loin.
  if (isHandoverActor(ticket, meId) && !sameId(ticket.assigneeId, meId)
      && roleHasMenu("/app/transmitted/tickets/$id", role)) {
    return "/app/transmitted/tickets/$id";
  }

  // 6. Mes tickets — je suis le requérant.
  if (sameId(ticket.requesterId, meId)) return "/app/requests/$id";

  // 7. Espace admin — l'admin voit tout, sans autre menu plus précis.
  if (role === "admin") return "/app/admin/tickets/$id";

  // 8. Repli : la fiche personnelle, ouverte à tous les rôles authentifiés.
  return "/app/requests/$id";
}
