import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/resolved_/tickets/$id")({
  beforeLoad: () => requireRole("chief-service", "technicien", "chef-division-support", "admin"),
  component: ResolvedTicketDetail,
});

function ResolvedTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="resolved" />;
}
