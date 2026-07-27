import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/chief-inbox_/tickets/$id")({
  beforeLoad: () => requireRole("chief-service", "admin"),
  head: () => ({ meta: [{ title: "Ticket chef de service — EDG Support" }] }),
  component: ChiefInboxTicketDetail,
});

function ChiefInboxTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="chiefInbox" />;
}
