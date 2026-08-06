import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/transmitted_/tickets/$id")({
  beforeLoad: () => requireRole("agent-support", "chief-service", "chief-departement", "director", "admin"),
  component: TransmittedTicketDetail,
});

function TransmittedTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="transmitted" />;
}
