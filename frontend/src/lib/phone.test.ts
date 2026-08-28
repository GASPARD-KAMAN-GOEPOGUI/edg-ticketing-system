import { describe, expect, it } from "vitest";
import {
  computePhoneEdit,
  formatGuineaPhoneDisplay,
  isValidGuineaPhone,
  normalizeGuineaPhone,
} from "./phone";

describe("normalizeGuineaPhone — les 3 formats convergent vers la même valeur canonique", () => {
  it.each([
    ["+224 622 12 34 56", "+224622123456"],
    ["224 622 12 34 56", "+224622123456"],
    ["622 12 34 56", "+224622123456"],
    ["+224622123456", "+224622123456"],
    ["224622123456", "+224622123456"],
    ["622123456", "+224622123456"],
    ["00224622123456", "+224622123456"], // parité avec backend/api/core/phone.py
  ])("%s → %s", (raw, expected) => {
    expect(normalizeGuineaPhone(raw)).toBe(expected);
  });

  it("valeur vide/absente → chaîne vide", () => {
    expect(normalizeGuineaPhone("")).toBe("");
    expect(normalizeGuineaPhone(null)).toBe("");
    expect(normalizeGuineaPhone(undefined)).toBe("");
  });
});

describe("isValidGuineaPhone", () => {
  it.each(["+224622123456", "+224 622 12 34 56", "224622123456", "622123456", "622 12 34 56"])(
    "accepte %s",
    (raw) => {
      expect(isValidGuineaPhone(raw)).toBe(true);
    },
  );

  it.each([
    ["+225622123456", "mauvais indicatif pays"],
    ["+223622123456", "mauvais indicatif pays"],
    ["+224522123456", "mauvais préfixe mobile (5 au lieu de 6)"],
    ["+224722123456", "mauvais préfixe mobile (7 au lieu de 6)"],
    ["+224612345", "numéro trop court"],
    ["+224622123456789", "numéro trop long"],
    ["abc", "pas un numéro"],
    ["+224ABC123456", "lettres mêlées aux chiffres"],
    ["224ABC123456", "lettres mêlées aux chiffres"],
    ["", "vide"],
    ["   ", "blanc"],
  ])("rejette %s (%s)", (raw) => {
    expect(isValidGuineaPhone(raw)).toBe(false);
  });
});

describe("formatGuineaPhoneDisplay — saisie progressive, format +224", () => {
  const steps = [
    "+",
    "+2",
    "+22",
    "+224",
    "+2246",
    "+22462",
    "+224622",
    "+2246221",
    "+22462212",
    "+224622123",
    "+2246221234",
    "+22462212345",
    "+224622123456",
  ];
  const expected = [
    "+",
    "+2",
    "+22",
    "+224",
    "+224 6",
    "+224 62",
    "+224 622",
    "+224 622 1",
    "+224 622 12",
    "+224 622 12 3",
    "+224 622 12 34",
    "+224 622 12 34 5",
    "+224 622 12 34 56",
  ];

  it.each(steps.map((s, i) => [s, expected[i]] as const))("%s → %s", (raw, want) => {
    expect(formatGuineaPhoneDisplay(raw)).toBe(want);
  });
});

describe("formatGuineaPhoneDisplay — saisie progressive, format local (sans indicatif)", () => {
  const steps = ["6", "62", "622", "6221", "62212", "622123", "6221234", "62212345", "622123456"];
  const expected = [
    "6",
    "62",
    "622",
    "622 1",
    "622 12",
    "622 12 3",
    "622 12 34",
    "622 12 34 5",
    "622 12 34 56",
  ];

  it.each(steps.map((s, i) => [s, expected[i]] as const))("%s → %s", (raw, want) => {
    expect(formatGuineaPhoneDisplay(raw)).toBe(want);
  });
});

describe("formatGuineaPhoneDisplay — format 224 sans +", () => {
  it("224622123456 → 224 622 12 34 56", () => {
    expect(formatGuineaPhoneDisplay("224622123456")).toBe("224 622 12 34 56");
  });

  it("un affichage déjà espacé reste stable (idempotent)", () => {
    expect(formatGuineaPhoneDisplay("224 622 12 34 56")).toBe("224 622 12 34 56");
    expect(formatGuineaPhoneDisplay("+224 622 12 34 56")).toBe("+224 622 12 34 56");
  });
});

describe("formatGuineaPhoneDisplay — collé (paste)", () => {
  it.each([
    ["+224622123456", "+224 622 12 34 56"],
    ["+224 622 12 34 56", "+224 622 12 34 56"],
    ["224622123456", "224 622 12 34 56"],
    ["622123456", "622 12 34 56"],
  ])("coller %s → %s", (pasted, want) => {
    expect(formatGuineaPhoneDisplay(pasted)).toBe(want);
  });
});

describe("formatGuineaPhoneDisplay — caractères invalides ignorés sans bloquer la saisie", () => {
  it("les lettres n'apparaissent jamais dans l'affichage", () => {
    expect(formatGuineaPhoneDisplay("+224abc622123456")).toBe("+224 622 12 34 56");
  });

  it("un + qui n'est pas en tête est ignoré", () => {
    expect(formatGuineaPhoneDisplay("622+123456")).toBe("622 12 34 56");
  });

  it("plusieurs + tapés ne produisent qu'un seul + affiché", () => {
    expect(formatGuineaPhoneDisplay("++224622123456")).toBe("+224 622 12 34 56");
  });
});

describe("computePhoneEdit — édition d'une valeur existante venant du backend", () => {
  it("+224622123456 est affiché lisiblement, valeur canonique conservée", () => {
    const display = formatGuineaPhoneDisplay("+224622123456");
    expect(display).toBe("+224 622 12 34 56");
    expect(normalizeGuineaPhone(display)).toBe("+224622123456");
  });
});

describe("computePhoneEdit — position du curseur", () => {
  it("insertion en fin de champ place le curseur en fin de texte reformaté", () => {
    // L'utilisateur tape "6" après avoir déjà "622" à l'écran → DOM = "6226", curseur en position 4.
    const result = computePhoneEdit("6226", 4);
    expect(result.display).toBe("622 6");
    expect(result.cursor).toBe(5); // juste après le "6" inséré, après l'espace auto
  });

  it("insertion au milieu du numéro conserve la position relative au chiffre tapé", () => {
    // Affichage avant : "622 12 34 56" (9 chiffres). L'utilisateur insère "9" entre
    // "622 1" et "2 34 56" → DOM brut = "6221923456", curseur juste après le 9 inséré (position 5).
    const result = computePhoneEdit("6221923456", 5);
    // 10 chiffres locaux maintenant (dépasse 9, donc format continue de grouper par 2) :
    expect(result.display).toBe("622 19 23 45 6");
    // 5 chiffres significatifs avant le curseur ("6","2","2","1","9") → même position après reformatage.
    const sigDigitsBeforeCursor = result.display
      .slice(0, result.cursor)
      .replace(/[^0-9]/g, "").length;
    expect(sigDigitsBeforeCursor).toBe(5);
  });

  it("Backspace sur le dernier chiffre retire un chiffre et recule le curseur", () => {
    // Affichage avant : "622 12 34 56", utilisateur backspace en fin de champ.
    // DOM après suppression native du dernier caractère ("6") = "62212345", curseur à la fin (8).
    const result = computePhoneEdit("62212345", 8);
    expect(result.display).toBe("622 12 34 5");
    expect(result.cursor).toBe(result.display.length);
  });

  it("Backspace supprimant un espace auto-inséré ne modifie pas les chiffres et repositionne le curseur", () => {
    // Affichage avant : "622 12". Curseur juste après l'espace (position 4, avant "12").
    // Backspace → le navigateur retire le caractère juste avant le curseur (l'espace) :
    // DOM après = "62212", curseur à la position 3 (où était l'espace).
    const result = computePhoneEdit("62212", 3);
    expect(result.display).toBe("622 12"); // mêmes chiffres, ré-affichés identiquement
    expect(result.cursor).toBe(3); // curseur juste avant "12", à l'endroit logique
  });

  it("suppression complète puis nouvelle saisie repart d'un champ vide propre", () => {
    const cleared = computePhoneEdit("", 0);
    expect(cleared.display).toBe("");
    expect(cleared.canonical).toBe("");
    expect(cleared.isValid).toBe(false);

    const restarted = computePhoneEdit("6", 1);
    expect(restarted.display).toBe("6");
    expect(restarted.cursor).toBe(1);
  });

  it("remplacement d'une sélection complète par un nouveau chiffre repart du bon curseur", () => {
    // Le champ contenait "622 12 34 56", tout sélectionné puis remplacé en tapant "6".
    // Le navigateur livre directement DOM = "6", curseur = 1.
    const result = computePhoneEdit("6", 1);
    expect(result.display).toBe("6");
    expect(result.cursor).toBe(1);
  });
});

describe("Validation stricte — la conversion finale est toujours +2246XXXXXXXX pour un numéro valide", () => {
  it.each([
    "+224622123456",
    "+224 622 12 34 56",
    "224622123456",
    "224 622 12 34 56",
    "622123456",
    "622 12 34 56",
  ])("%s → +224622123456", (raw) => {
    expect(normalizeGuineaPhone(raw)).toBe("+224622123456");
    expect(isValidGuineaPhone(raw)).toBe(true);
  });
});
