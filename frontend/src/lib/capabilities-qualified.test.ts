import { describe, expect, it } from "vitest";
import { canTicketAction } from "./capabilities";
import { statusLabels } from "./mock-data";

describe("statut « Qualifié » (orienté vers un chef de division, 2026-10-14)", () => {
  it("libellé affiché", () => {
    expect(statusLabels.qualified).toBe("Qualifié");
  });

  it("annuler, rejeter, changer la priorité restent possibles, comme en qualification", () => {
    for (const action of ["cancel", "reject", "change_priority"] as const) {
      expect(canTicketAction("admin", action, "qualified")).toBe(canTicketAction("admin", action, "qualifying"));
      expect(canTicketAction("admin", action, "qualified")).toBe(true);
    }
  });

  it("le demandeur ne modifie plus un ticket déjà qualifié", () => {
    expect(canTicketAction("user", "requester_edit", "qualifying", { isRequester: true })).toBe(true);
    expect(canTicketAction("user", "requester_edit", "qualified", { isRequester: true })).toBe(false);
  });
});
