import { describe, expect, it } from "vitest";
import {
  MOBILE_SHORTCUTS,
  PERSONAL_SPACE_ROUTE,
  TREATMENT_BOX_ROUTES,
  bestMatchingRoute,
  mobileShortcutsFor,
} from "./mobile-shortcuts";

/** Rôles disposant d'une barre dédiée. */
const ROLES = Object.keys(MOBILE_SHORTCUTS);
/** Rôles humains du workflow — l'admin est un rôle d'administration, pas un
 *  acteur du traitement : sa barre porte ses outils, pas l'espace personnel. */
const WORKFLOW_ROLES = ROLES.filter((r) => r !== "admin");

describe("barre mobile — « Mes tickets » et « Ma boîte » ne doivent jamais être confondus", () => {
  // C'est LE piège de ce fichier : /app/my-tickets s'appelle « Ma boîte de
  // traitement », alors que l'espace personnel est /app/requests. La barre du
  // bas avait dérivé exactement là (libellé « Mes tickets » sur la boîte de
  // traitement, pour 3 rôles).
  it.each(ROLES)("%s — aucune entrée de traitement n'est libellée « Mes tickets »", (role) => {
    for (const item of MOBILE_SHORTCUTS[role]) {
      if ((TREATMENT_BOX_ROUTES as readonly string[]).includes(item.to)) {
        expect(item.label).not.toBe("Mes tickets");
      }
    }
  });

  it.each(ROLES)("%s — « Mes tickets » ne pointe que vers l'espace personnel", (role) => {
    for (const item of MOBILE_SHORTCUTS[role]) {
      if (item.label === "Mes tickets") {
        expect(item.to).toBe(PERSONAL_SPACE_ROUTE);
      }
    }
  });
});

describe("barre mobile — composition par rôle", () => {
  it.each(WORKFLOW_ROLES)("%s — l'espace personnel reste accessible", (role) => {
    // Chaque acteur, quel que soit son rôle, crée et suit ses propres demandes.
    const routes = MOBILE_SHORTCUTS[role].map((i) => i.to);
    expect(routes).toContain(PERSONAL_SPACE_ROUTE);
  });

  it.each(ROLES)("%s — Notifications et Profil ferment la barre", (role) => {
    const shortcuts = MOBILE_SHORTCUTS[role];
    const routes = shortcuts.map((item) => item.to);
    expect(routes.slice(-2)).toEqual(["/app/notifications", "/app/profile"]);
    expect(shortcuts.find((item) => item.to === "/app/notifications")?.label).toBe(
      "Notifications",
    );
  });

  it.each(ROLES)("%s — exactement une entrée mise en avant", (role) => {
    const primaries = MOBILE_SHORTCUTS[role].filter((i) => i.primary);
    expect(primaries).toHaveLength(1);
  });

  it.each(ROLES)("%s — cinq entrées au maximum (lisibilité ~360 px)", (role) => {
    expect(MOBILE_SHORTCUTS[role].length).toBeLessThanOrEqual(5);
  });

  it.each(ROLES)("%s — aucune route en double", (role) => {
    const routes = MOBILE_SHORTCUTS[role].map((i) => i.to);
    expect(new Set(routes).size).toBe(routes.length);
  });
});

describe("barre mobile — geste central de chaque rôle (procédure EDG/PS-GSI/Pro-02)", () => {
  it.each([
    ["user", "/app/new"],                          // 1.1 — transmettre une réquisition
    ["chief-service", "/app/queue"],               // 1.2/1.3 — qualifier puis imputer
    ["chef-division-support", "/app/distribution"], // 1.4 — affecter à un technicien
    ["technicien", "/app/my-tickets"],             // 2.x/3.x — résoudre, établir le PV
  ])("%s — l'entrée mise en avant est %s", (role, route) => {
    const primary = MOBILE_SHORTCUTS[role].find((i) => i.primary);
    expect(primary?.to).toBe(route);
  });

  it("le directeur traite dans /app/direction, pas dans /app/my-tickets", () => {
    const routes = MOBILE_SHORTCUTS.director.map((i) => i.to);
    expect(routes).toContain("/app/direction");
    expect(routes).not.toContain("/app/my-tickets");
  });

  it("« Rapports » ne réapparaît nulle part (masqué de la navigation en 2026-08)", () => {
    for (const role of ROLES) {
      expect(MOBILE_SHORTCUTS[role].map((i) => i.to)).not.toContain("/app/reports");
    }
  });
});

describe("mobileShortcutsFor — repli", () => {
  it("un rôle inconnu ou absent retombe sur la barre de l'utilisateur simple", () => {
    expect(mobileShortcutsFor("role-inexistant")).toBe(MOBILE_SHORTCUTS.user);
    expect(mobileShortcutsFor(undefined)).toBe(MOBILE_SHORTCUTS.user);
  });

  it("chaque rôle connu reçoit bien sa propre barre", () => {
    for (const role of ROLES) {
      expect(mobileShortcutsFor(role)).toBe(MOBILE_SHORTCUTS[role]);
    }
  });
});

describe("bestMatchingRoute — même règle de menu actif sur tous les écrans", () => {
  const routes = ["/app", "/app/requests", "/app/queue", "/app/my-tickets", "/app/new"];

  it("Accueil n'est actif que sur /app exactement", () => {
    expect(bestMatchingRoute("/app", routes)).toBe("/app");
    expect(bestMatchingRoute("/app/queue", routes)).toBe("/app/queue");
  });

  it("une sous-page allume son menu parent", () => {
    expect(bestMatchingRoute("/app/queue/tickets/12", routes)).toBe("/app/queue");
  });

  it("frontière « / » : un préfixe sans séparateur ne correspond pas", () => {
    expect(bestMatchingRoute("/app/requests-archive", routes)).toBeNull();
  });

  it("la route la plus précise l'emporte", () => {
    expect(bestMatchingRoute("/app/requests/history", [...routes, "/app/requests/history"])).toBe(
      "/app/requests/history",
    );
  });

  it("aucune correspondance → null", () => {
    expect(bestMatchingRoute("/app/profile", routes)).toBeNull();
  });
});
