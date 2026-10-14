import { describe, expect, it } from "vitest";
import { chiefQualification } from "./chief-qualification";

describe("qualification du chef de service (onglet Description)", () => {
  it("valeurs figées à la qualification, même si le technicien a requalifié", () => {
    expect(chiefQualification({
      infos: { qualified_category: "reseau", qualified_priority: "high", qualified_at: "2026-10-14T09:00:00+00:00", receiver_name: "Mamadou Diallo" },
      category: "materiel", priority: "critical", inTriage: false,
    })).toEqual({ pending: false, category: "reseau", priority: "high", by: "Mamadou Diallo", at: "2026-10-14T09:00:00+00:00" });
  });

  it("pas encore qualifié : en attente", () => {
    expect(chiefQualification({ infos: {}, inTriage: true, category: "autre", priority: "medium" }))
      .toEqual({ pending: true });
  });

  it("ticket qualifié avant le figeage : valeur d'avant la requalification du technicien", () => {
    expect(chiefQualification({
      infos: { receiver_name: "Mamadou Diallo" }, inTriage: false, category: "materiel", priority: "critical",
      timeline: [
        { type: "created" },
        { type: "field_check", infos: { requalified: true, previous_category: "reseau", previous_priority: null } },
      ],
    })).toEqual({ pending: false, category: "reseau", priority: "critical", by: "Mamadou Diallo" });
  });

  it("ticket qualifié avant le figeage, sans requalification : valeurs actuelles", () => {
    expect(chiefQualification({ inTriage: false, category: "reseau", priority: "high" }))
      .toEqual({ pending: false, category: "reseau", priority: "high", by: undefined });
  });
});
