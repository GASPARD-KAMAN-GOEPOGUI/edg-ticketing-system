import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/queue_/tickets/$id")({
  beforeLoad: () => requireRole("agent-support", "chief-service", "admin"),
  head: () => ({ meta: [{ title: "Ticket en file d'attente — EDG Support" }] }),
  component: QueueTicketDetail,
});

function QueueTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="queue" />;
}
