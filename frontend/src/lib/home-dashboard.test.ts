import { describe, expect, it } from "vitest";

import { computeHomeCounts, donutSegments, RECENT_EXCLUDED_STATUSES } from "./home-dashboard";
import { INVALIDATION_MAP } from "./realtime/invalidation-map";

describe("computeHomeCounts — compteurs de l'accueil", () => {
  it("reprend exactement les règles de l'ancien calcul client", () => {
    const counts = computeHomeCounts(
      { new: 2, in_progress: 3, resolved: 4, closed: 5, cancelled: 1, rejected: 2 },
      17,
    );
    expect(counts).toEqual({
      total: 17,
      active: 2 + 3 + 4, // un ticket résolu attend encore sa validation
      done: 4 + 5,
      cancelled: 1,
    });
  });

  it("n'a plus de plafond : au-delà de 100 tickets les comptes restent exacts", () => {
    expect(computeHomeCounts({ new: 250 }, 250).active).toBe(250);
  });

  it("tolère des statuts absents", () => {
    expect(computeHomeCounts({}, 0)).toEqual({ total: 0, active: 0, done: 0, cancelled: 0 });
  });
});

describe("donutSegments — anneau SVG", () => {
  it("répartit la circonférence proportionnellement, sans chevauchement", () => {
    const segs = donutSegments({ new: 1, closed: 3 }, 0);
    expect(segs.map((s) => [s.key, s.length, s.offset])).toEqual([
      ["new", 0.25, 0],
      ["closed", 0.75, 0.25],
    ]);
  });

  it("ignore les statuts à zéro et renvoie [] sans donnée", () => {
    expect(donutSegments({ new: 0 })).toEqual([]);
    expect(donutSegments({ new: 0, closed: 2 }).map((s) => s.key)).toEqual(["closed"]);
  });

  it("un seul statut forme un anneau complet (pas d'espacement)", () => {
    expect(donutSegments({ new: 5 })[0].length).toBe(1);
  });
});

describe("accueil temps réel", () => {
  it("tout événement request.* rafraîchit les compteurs et les tickets récents", () => {
    for (const type of ["request.created", "request.status_changed", "request.cancelled"]) {
      const keys = INVALIDATION_MAP[type].map((k) => JSON.stringify(k));
      expect(keys).toContain(JSON.stringify(["my-requests-stats"]));
      expect(keys).toContain(JSON.stringify(["my-requests"]));
    }
  });

  it("les tickets récents excluent les statuts terminaux côté serveur", () => {
    expect(RECENT_EXCLUDED_STATUSES.split(",")).toEqual(
      expect.arrayContaining(["closed", "cancelled", "rejected"]),
    );
  });
});
