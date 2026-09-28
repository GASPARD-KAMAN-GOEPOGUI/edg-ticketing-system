import type { Role } from "@/lib/mock-data";

export type TicketDetailRoute =
  | "/app/requests/$id"
  | "/app/history/tickets/$id"
  | "/app/supervision/tickets/$id"
  | "/app/queue/tickets/$id"
  | "/app/transmitted/tickets/$id"
  | "/app/my-tickets/tickets/$id"
  | "/app/distribution/tickets/$id"
  | "/app/dg/tickets/$id"
  | "/app/sla-center/tickets/$id"
  | "/app/admin/tickets/$id";

export type TicketListRoute =
  | "/app/requests"
  | "/app/history"
  | "/app/supervision"
  | "/app/queue"
  | "/app/transmitted"
  | "/app/my-tickets"
  | "/app/distribution"
  | "/app/dg"
  | "/app/sla-center"
  | "/app/admin/users";

export function ticketDetailRouteForList(route: TicketListRoute): TicketDetailRoute {
  if (route === "/app/supervision") return "/app/supervision/tickets/$id";
  if (route === "/app/queue") return "/app/queue/tickets/$id";
  if (route === "/app/transmitted") return "/app/transmitted/tickets/$id";
  if (route === "/app/history") return "/app/history/tickets/$id";
  if (route === "/app/my-tickets") return "/app/my-tickets/tickets/$id";
  if (route === "/app/distribution") return "/app/distribution/tickets/$id";
  if (route === "/app/dg") return "/app/dg/tickets/$id";
  if (route === "/app/sla-center") return "/app/sla-center/tickets/$id";
  if (route === "/app/admin/users") return "/app/admin/tickets/$id";
  return "/app/requests/$id";
}

function ticketDetailRouteForRole(role?: Role): TicketDetailRoute {
  if (role === "chief-service" || role === "technicien" || role === "chef-division-support") return "/app/my-tickets/tickets/$id";
  if (role === "admin") return "/app/admin/tickets/$id";
  return "/app/requests/$id";
}

function explicitTicketDetailRouteFromSource(source?: string | null): TicketDetailRoute | null {
  const value = (source ?? "").toLowerCase();

  if (value.includes("/app/requests")) return "/app/requests/$id";
  if (value.includes("/app/history")) return "/app/history/tickets/$id";
  if (value.includes("/app/supervision")) return "/app/supervision/tickets/$id";
  if (value.includes("/app/queue")) return "/app/queue/tickets/$id";
  if (value.includes("/app/transmitted")) return "/app/transmitted/tickets/$id";
  if (value.includes("/app/my-tickets")) return "/app/my-tickets/tickets/$id";
  if (value.includes("/app/distribution")) return "/app/distribution/tickets/$id";
  if (value.includes("/app/dg")) return "/app/dg/tickets/$id";
  if (value.includes("/app/sla-center")) return "/app/sla-center/tickets/$id";
  if (value.includes("/app/admin")) return "/app/admin/tickets/$id";

  return null;
}

export function ticketDetailRouteForSource(source?: string | null, role?: Role): TicketDetailRoute {
  return explicitTicketDetailRouteFromSource(source) ?? ticketDetailRouteForRole(role);
}

export function ticketDetailRouteForNotification(source?: string | null, role?: Role): TicketDetailRoute {
  const explicitRoute = explicitTicketDetailRouteFromSource(source);
  if (explicitRoute && explicitRoute !== "/app/requests/$id") return explicitRoute;
  if (role === "user" || role === "public") return "/app/requests/$id";
  return ticketDetailRouteForRole(role);
}
