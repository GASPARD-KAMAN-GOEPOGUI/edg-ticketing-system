import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { RequestDetailPage } from "./app.requests.$id";

export const Route = createFileRoute("/app/department-inbox_/tickets/$id")({
  beforeLoad: () => requireRole("chief-departement", "admin"),
  head: () => ({ meta: [{ title: "Ticket chef de département — EDG Support" }] }),
  component: DepartmentInboxTicketDetail,
});

function DepartmentInboxTicketDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="departmentInbox" />;
}
