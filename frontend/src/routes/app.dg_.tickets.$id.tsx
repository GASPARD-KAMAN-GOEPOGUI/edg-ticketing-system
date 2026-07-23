import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/dg_/tickets/$id")({
  beforeLoad: () => requireRole("admin"),
  head: () => ({ meta: [{ title: "Ticket global — EDG Support" }] }),
  component: DgTicketDetail,
});

function DgTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="dg" />;
}
