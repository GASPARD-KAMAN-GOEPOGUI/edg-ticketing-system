import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/admin/tickets/$id")({
  beforeLoad: () => requireRole("admin"),
  head: () => ({ meta: [{ title: "Ticket administre — EDG Support" }] }),
  component: AdminTicketDetail,
});

function AdminTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="admin" />;
}
