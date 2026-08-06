import { createFileRoute } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/history_/tickets/$id")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Ticket historique — EDG Support" }] }),
  component: HistoryTicketDetail,
});

function HistoryTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="history" />;
}
