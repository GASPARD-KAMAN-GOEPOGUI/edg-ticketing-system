import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { AggregatedServiceDashboard } from "@/components/aggregated-service-dashboard";

// Lot 4 — "Tableau de bord stratégique" : vue consultative agrégée pour Direction DSI
// (rôle director uniquement). Additive — coexiste avec /app/direction et
// /app/supervision sans rien leur retirer. Réutilise AggregatedServiceDashboard
// (Lot 3) en mode "strategic" : lecture seule, pas de drill-down, pas d'action.
export const Route = createFileRoute("/app/strategic-dashboard")({
  beforeLoad: () => requireRole("director"),
  head: () => ({ meta: [{ title: "Tableau de bord stratégique — EDG Support" }] }),
  component: StrategicDashboardPage,
});

function StrategicDashboardPage() {
  return (
    <div className="mx-auto max-w-7xl">
      <AggregatedServiceDashboard mode="strategic" />
    </div>
  );
}
