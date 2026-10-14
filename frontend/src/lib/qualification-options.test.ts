import { describe, expect, it } from "vitest";
import { categoryOptions, labelOf, priorityOptions } from "./qualification-options";

describe("listes de qualification (référentiels de la base)", () => {
  it("catégories : libellé affiché, code envoyé, inactives et supprimées exclues, ordre respecté", () => {
    const options = categoryOptions([
      { code: "materiel", label: "Matériel", status: true, sort_order: 7 },
      { code: "reseau", label: "Réseau", status: true, sort_order: 4 },
      { code: "ancienne", label: "Ancienne", status: false, sort_order: 1 },
      { code: "supprimee", label: "Supprimée", status: true, deleted_at: "2026-01-01", sort_order: 2 },
    ]);
    expect(options).toEqual([
      { value: "reseau", label: "Réseau" },
      { value: "materiel", label: "Matériel" },
    ]);
  });

  it("priorités : le slug est la valeur envoyée", () => {
    expect(priorityOptions({ items: [{ slug: "high", label: "Haute", status: true, sort_order: 3 }] }))
      .toEqual([{ value: "high", label: "Haute" }]);
  });

  it("libellé d'un code, ou le code s'il est inconnu", () => {
    const options = [{ value: "reseau", label: "Réseau" }];
    expect(labelOf(options, "reseau")).toBe("Réseau");
    expect(labelOf(options, "autre")).toBe("autre");
    expect(labelOf(options, undefined)).toBe("");
  });
});
