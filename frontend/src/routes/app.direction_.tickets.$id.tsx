import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/direction_/tickets/$id")({
  beforeLoad: () => requireRole("director", "admin"),
  head: () => ({ meta: [{ title: "Ticket direction — EDG Support" }] }),
  component: DirectionTicketDetail,
});

function DirectionTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="direction" />;
}
