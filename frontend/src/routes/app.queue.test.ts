import { describe, expect, it } from "vitest";

import { queueTargetLabel } from "./app.queue";

describe("queueTargetLabel — liste des chefs de division support", () => {
  it("affiche « nom complet.badge » quand le badge est renseigné", () => {
    expect(
      queueTargetLabel({ firstname: "Mamadou", name: "Diallo", matricule: "EDG-00412" }),
    ).toBe("Mamadou Diallo.EDG-00412");
  });

  it("distingue deux homonymes par leur badge", () => {
    const a = queueTargetLabel({ firstname: "Alpha", name: "Bah", matricule: "EDG-001" });
    const b = queueTargetLabel({ firstname: "Alpha", name: "Bah", matricule: "EDG-002" });
    expect(a).not.toBe(b);
  });

  it("n'affiche que le nom complet, sans point orphelin, quand le badge manque", () => {
    expect(queueTargetLabel({ firstname: "Ousmane", name: "Camara" })).toBe("Ousmane Camara");
    expect(queueTargetLabel({ firstname: "Ousmane", name: "Camara", matricule: "" })).toBe(
      "Ousmane Camara",
    );
    // Un badge fait uniquement d'espaces ne doit pas produire « Nom. »
    expect(queueTargetLabel({ firstname: "Ousmane", name: "Camara", matricule: "   " })).toBe(
      "Ousmane Camara",
    );
  });

  it("se contente du nom quand le prénom est absent", () => {
    expect(queueTargetLabel({ name: "Camara", matricule: "EDG-00873" })).toBe("Camara.EDG-00873");
    expect(queueTargetLabel({ name: "Camara" })).toBe("Camara");
  });
});
