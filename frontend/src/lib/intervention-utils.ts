// BR-TRACE-001 — helpers partagés entre InterventionJournal, InterventionFilters
// et InterventionDetailsModal (évite un import circulaire entre ces composants).
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { roleLabels } from "@/lib/mock-data";
import type { Intervention, Role } from "@/lib/mock-data";

export function formatInterventionDateTime(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return format(date, "d MMM yyyy HH:mm", { locale: fr });
}

export function formatInterventionDuration(seconds?: number): string {
  if (seconds == null || seconds < 0) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  if (h === 0) return `${m} min`;
  return m > 0 ? `${h} h ${m} min` : `${h} h`;
}

export function interventionRoleLabel(role?: string): string | undefined {
  if (!role) return undefined;
  return roleLabels[role as Role] ?? role;
}

// Statut réel d'une intervention, dérivé uniquement de `decision` (déjà
// enregistré) — aucun statut inventé (pas de "Interrompue"/"En attente",
// absents du modèle actuel).
export type InterventionStatus = "ongoing" | "transmitted" | "resolved";

export function interventionStatus(iv: Intervention): InterventionStatus {
  if (iv.decision === "transmission") return "transmitted";
  if (iv.decision === "resolution") return "resolved";
  return "ongoing";
}

export const INTERVENTION_STATUS_LABEL: Record<InterventionStatus, string> = {
  ongoing: "En cours",
  transmitted: "Transmise",
  resolved: "Traitement terminé",
};

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}
