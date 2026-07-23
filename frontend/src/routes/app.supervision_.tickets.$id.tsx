import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/supervision_/tickets/$id")({
  beforeLoad: () => requireRole("chief", "director", "admin"),
  head: () => ({ meta: [{ title: "Dossier supervise — EDG Support" }] }),
  component: SupervisionTicketDetail,
});

function SupervisionTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="supervision" />;
}
