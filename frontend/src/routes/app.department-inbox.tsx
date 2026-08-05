import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { requireRole } from "@/lib/auth-guard";
import { AggregatedServiceDashboard } from "@/components/aggregated-service-dashboard";
import { ChiefInbox } from "./app.chief-inbox";

// Espace dédié au chief-departement — "Centre de pilotage" (Lot 3.4) : la vue
// agrégée par service est l'écran principal ; un clic sur un service ouvre un
// drill-down vers la même interface de traitement que chief-service
// (`ChiefInbox`, réutilisée avec un filtre de service — `filterUnitId`), sans
// dupliquer le composant. Route et garde de rôle propres à ce contexte.
function DepartmentInboxPage() {
  const [selectedUnit, setSelectedUnit] = useState<{ id: string; label: string } | null>(null);

  if (selectedUnit) {
    return (
      <ChiefInbox
        filterUnitId={selectedUnit.id}
        onBackToOverview={() => setSelectedUnit(null)}
      />
    );
  }

  return (
    <div className="mx-auto max-w-7xl">
      <AggregatedServiceDashboard
        mode="pilotage"
        onSelectService={(unitId, label) => setSelectedUnit({ id: unitId, label })}
      />
    </div>
  );
}

export const Route = createFileRoute("/app/department-inbox")({
  beforeLoad: () => requireRole("chief-departement", "admin"),
  head: () => ({ meta: [{ title: "Centre de pilotage — Département — EDG Support" }] }),
  component: DepartmentInboxPage,
});
