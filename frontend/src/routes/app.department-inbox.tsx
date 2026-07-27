import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { ChiefInbox } from "./app.chief-inbox";

// Espace dédié au chief-departement — même interface que la boîte de
// traitement du chief-service (`app.chief-inbox.tsx`), mais route et garde de
// rôle propres : le composant partagé détecte l'espace via l'URL courante
// pour élargir le périmètre de données au département entier.
export const Route = createFileRoute("/app/department-inbox")({
  beforeLoad: () => requireRole("chief-departement", "admin"),
  head: () => ({ meta: [{ title: "Boîte de traitement — Département — EDG Support" }] }),
  component: ChiefInbox,
});
