import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/sla-center_/tickets/$id")({
  beforeLoad: () => requireRole("chief-service", "chief-departement", "director", "admin"),
  head: () => ({ meta: [{ title: "Ticket centre SLA — EDG Support" }] }),
  component: SlaTicketDetail,
});

function SlaTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="slaCenter" />;
}
