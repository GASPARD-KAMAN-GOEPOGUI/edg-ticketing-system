import { describe, expect, it } from "vitest";

import { bellSnapshot, hasNewActivity, parseRealtimeMode } from "./polling";

const snap = (total: number, newestUnreadId: number | null) => ({ total, newestUnreadId });

describe("parseRealtimeMode", () => {
  it("vaut sse par défaut et polling seulement si demandé", () => {
    expect(parseRealtimeMode(undefined)).toBe("sse");
    expect(parseRealtimeMode("")).toBe("sse");
    expect(parseRealtimeMode("autre")).toBe("sse");
    expect(parseRealtimeMode(" Polling ")).toBe("polling");
  });
});

describe("bellSnapshot", () => {
  it("lit le total et l'identifiant de la dernière notification non lue", () => {
    expect(bellSnapshot({ total: 3, items: [{ id: "42" }] })).toEqual(snap(3, 42));
    expect(bellSnapshot({ total: 0, items: [] })).toEqual(snap(0, null));
    expect(bellSnapshot(undefined)).toBeNull();
  });
});

describe("hasNewActivity", () => {
  it("premier relevé : pas de nouveauté (rien à comparer)", () => {
    expect(hasNewActivity(null, snap(2, 10))).toBe(false);
  });

  it("aucun changement : pas de nouveauté", () => {
    expect(hasNewActivity(snap(2, 10), snap(2, 10))).toBe(false);
  });

  it("une notification arrive : nouveauté", () => {
    expect(hasNewActivity(snap(2, 10), snap(3, 11))).toBe(true);
    expect(hasNewActivity(snap(0, null), snap(1, 11))).toBe(true);
  });

  it("une arrive pendant qu'une autre est lue (même total) : nouveauté", () => {
    expect(hasNewActivity(snap(2, 10), snap(2, 11))).toBe(true);
  });

  it("lecture de la plus récente ou de toutes : pas de nouveauté", () => {
    expect(hasNewActivity(snap(2, 10), snap(1, 9))).toBe(false);
    expect(hasNewActivity(snap(2, 10), snap(0, null))).toBe(false);
  });
});
