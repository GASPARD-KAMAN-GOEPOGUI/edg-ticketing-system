import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/my-tickets_/tickets/$id")({
  beforeLoad: () => requireRole("chief-service", "technicien", "chef-division-support", "admin"),
  head: () => ({ meta: [{ title: "Ticket a traiter — EDG Support" }] }),
  component: MyTicketDetail,
});

function MyTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="myTickets" />;
}
