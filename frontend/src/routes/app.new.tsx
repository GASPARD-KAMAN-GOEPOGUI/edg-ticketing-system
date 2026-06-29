import { createFileRoute } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";

// Tout employé connecté peut soumettre une demande (Algo 2 — can("submit_request")).
// Le form est rendu en Dialog par le layout parent app.tsx.
// Le requester_id est forcé depuis le JWT côté backend (C-02) — aucun rôle ne peut usurper.
export const Route = createFileRoute("/app/new")({
  head: () => ({ meta: [{ title: "Nouvelle demande — EDG Support" }] }),
  beforeLoad: () => requireAuth(),
  component: () => null,
});
