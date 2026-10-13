import { describe, expect, it } from "vitest";
import { agentFullName, agentInitials, agentLabel, matchesAgentSearch } from "./agent-picker";

const fatoumata = { name: "CAMARA", firstname: "Fatoumata", matricule: "EDG-0815" };
const sekou = { name: "Camara", firstname: "Sékou", matricule: null };
const kolie = { name: "Kolié", firstname: undefined, matricule: "EDG-1200" };

describe("liste « Réassigner le ticket »", () => {
  it("affiche le nom complet suivi du badge", () => {
    expect(agentLabel(fatoumata)).toBe("Fatoumata CAMARA · EDG-0815");
  });

  it("sans badge : le nom complet seul", () => {
    expect(agentLabel(sekou)).toBe("Sékou Camara");
    expect(agentFullName(kolie)).toBe("Kolié");
  });

  it("initiales du prénom et du nom", () => {
    expect(agentInitials(fatoumata)).toBe("FC");
    expect(agentInitials(kolie)).toBe("KO");
  });

  it("recherche par prénom, nom ou badge, sans majuscules ni accents", () => {
    expect(matchesAgentSearch(fatoumata, "fatou")).toBe(true);
    expect(matchesAgentSearch(fatoumata, "0815")).toBe(true);
    expect(matchesAgentSearch(sekou, "SEKOU camara")).toBe(true);
    expect(matchesAgentSearch(kolie, "kolie")).toBe(true);
    expect(matchesAgentSearch(sekou, "fatou")).toBe(false);
    expect(matchesAgentSearch(sekou, "   ")).toBe(true);
  });
});
