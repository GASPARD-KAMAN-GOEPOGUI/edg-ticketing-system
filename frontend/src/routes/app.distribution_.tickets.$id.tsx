import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/distribution_/tickets/$id")({
  beforeLoad: () => requireRole("chef-division-support", "admin"),
  head: () => ({ meta: [{ title: "Ticket à répartir — EDG Support" }] }),
  component: DistributionTicketDetail,
});

function DistributionTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="distribution" />;
}
