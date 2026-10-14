import * as React from "react";
import { describe, expect, it } from "vitest";
import { collectItems, matchesSearch, nodeText } from "./select-utils";

function Item(_: { value: string; children?: React.ReactNode }) {
  return null;
}
function Other(_: { children?: React.ReactNode }) {
  return null;
}

describe("listes déroulantes avec recherche", () => {
  it("recherche sans majuscules ni accents, mot par mot", () => {
    expect(matchesSearch("Réseau", "res")).toBe(true);
    expect(matchesSearch("Habilitation / Accès", "acces habil")).toBe(true);
    expect(matchesSearch("Matériel", "reseau")).toBe(false);
    expect(matchesSearch("Matériel", "   ")).toBe(true);
  });

  it("texte d'un libellé composé d'éléments", () => {
    expect(nodeText(React.createElement("span", null, "Fatoumata ", React.createElement("b", null, "CAMARA"), " · ", 815)))
      .toBe("Fatoumata CAMARA · 815");
  });

  it("retrouve les choix, même imbriqués ou générés par une liste", () => {
    const tree = React.createElement(
      "div",
      null,
      React.createElement(Item, { value: "all" }, "Tout"),
      React.createElement(Other, null, "Groupe"),
      [1, 2].map((n) => React.createElement(Item, { key: n, value: `s${n}` }, `Service ${n}`)),
    );
    const items = collectItems(tree, Item);
    expect([...items.keys()]).toEqual(["all", "s1", "s2"]);
    expect(items.get("s2")?.text).toBe("Service 2");
  });
});
