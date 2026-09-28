/**
 * Raccourcis de la barre du bas mobile — le geste central de chaque rôle dans le
 * traitement d'un ticket (procédure EDG/PS-GSI/Pro-02), accessible en un appui
 * plutôt qu'à travers le tiroir.
 *
 * Ce n'est PAS une restriction : le tiroir (hamburger) et la sidebar se
 * construisent depuis `navItems` (app-layout.tsx) et restent exhaustifs pour le
 * rôle. Cette barre ne fait que raccourcir.
 *
 * Module séparé — et non un bloc de `app-layout.tsx` — pour être testable : le
 * runner Vitest du projet est volontairement sans JSX (`src/**\/*.test.ts`,
 * environnement node), il ne peut donc pas importer un composant `.tsx`. Voir
 * `mobile-shortcuts.test.ts`, qui verrouille les invariants ci-dessous.
 *
 * Règles de composition :
 *   - l'entrée `primary` est le geste central du rôle (mise en avant visuelle) ;
 *   - « Mes tickets » (/app/requests) figure dans toutes les barres des rôles
 *     humains : chaque acteur, quel que soit son rôle, reste demandeur de ses
 *     propres tickets. À ne JAMAIS confondre avec « Ma boîte »
 *     (/app/my-tickets), qui est l'espace de TRAITEMENT ;
 *   - « Alertes » et « Profil » ferment la barre pour tous ;
 *   - cinq entrées au maximum, pour rester lisible autour de 360 px.
 */
import {
  Activity,
  Bell,
  Inbox,
  LayoutDashboard,
  ListChecks,
  Plus,
  Settings,
  Share2,
  ShieldAlert,
  Ticket,
  Users2,
} from "lucide-react";

export type MobileShortcut = {
  to: string;
  icon: typeof LayoutDashboard;
  label: string;
  primary?: boolean;
};

/** Espace personnel de création/suivi — « Mes tickets ». */
export const PERSONAL_SPACE_ROUTE = "/app/requests";
/** Espace de traitement — « Ma boîte ». Ne jamais libeller « Mes tickets ». */
export const TREATMENT_BOX_ROUTES = ["/app/my-tickets"] as const;

const ALERTS: MobileShortcut = { to: "/app/notifications", icon: Bell, label: "Alertes" };
const PROFILE: MobileShortcut = { to: "/app/profile", icon: Settings, label: "Profil" };
const MY_REQUESTS: MobileShortcut = { to: PERSONAL_SPACE_ROUTE, icon: Inbox, label: "Mes tickets" };
const MY_BOX: MobileShortcut = { to: "/app/my-tickets", icon: Ticket, label: "Ma boîte" };

export const MOBILE_SHORTCUTS: Record<string, MobileShortcut[]> = {
  // Tâches 1.1 / 3.2 — transmettre une réquisition, puis valider le dépannage
  // (la signature du PV est hors périmètre projet, décision du 2026-09-22).
  user: [
    { to: "/app", icon: LayoutDashboard, label: "Accueil" },
    { to: "/app/new", icon: Plus, label: "Créer", primary: true },
    MY_REQUESTS, ALERTS, PROFILE,
  ],
  // Tâches 1.2 / 1.3 — réceptionner, analyser, qualifier, puis imputer au CDS.
  "chief-service": [
    { to: "/app/queue", icon: ListChecks, label: "File att.", primary: true },
    MY_BOX, MY_REQUESTS, ALERTS, PROFILE,
  ],
  // Tâches 1.4 / 3.4 — recevoir et affecter à un technicien, archiver le PV.
  "chef-division-support": [
    { to: "/app/distribution", icon: Share2, label: "Distrib.", primary: true },
    MY_BOX, MY_REQUESTS, ALERTS, PROFILE,
  ],
  // Tâches 1.5 / 2.x / 3.1 / 3.3 — préparer, qualifier, résoudre, établir le PV.
  technicien: [
    { ...MY_BOX, primary: true },
    MY_REQUESTS, ALERTS, PROFILE,
  ],
  admin: [
    { to: "/app", icon: LayoutDashboard, label: "Accueil" },
    { to: "/app/admin/users", icon: Users2, label: "Utilisateurs", primary: true },
    { to: "/app/admin/logs", icon: Activity, label: "Journaux" },
    ALERTS, PROFILE,
  ],
};

/** Raccourcis du rôle, avec repli sur ceux de l'utilisateur simple. */
export function mobileShortcutsFor(role: string | undefined): MobileShortcut[] {
  return MOBILE_SHORTCUTS[role ?? ""] ?? MOBILE_SHORTCUTS.user;
}
