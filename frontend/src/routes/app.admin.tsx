import { createFileRoute, Outlet } from "@tanstack/react-router";
import { requireAdmin } from "@/lib/auth-guard";

export const Route = createFileRoute("/app/admin")({
  beforeLoad: () => requireAdmin(),
  component: () => <Outlet />,
});
