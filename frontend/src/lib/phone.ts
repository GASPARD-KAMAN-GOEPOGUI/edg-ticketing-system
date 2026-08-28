// Numéro mobile guinéen — normalisation, formatage d'affichage et validation.
// Miroir exact de backend/api/core/phone.py (normalize_phone / validate_guinea_phone) :
// toute évolution du format canonique doit être répercutée des deux côtés.
//
// Formats acceptés à la saisie : +224 6XX XX XX XX, 224 6XX XX XX XX, 6XX XX XX XX
// (avec ou sans espaces). Format canonique (valeur métier, jamais d'espaces) :
// +2246XXXXXXXX — indicatif +224, préfixe mobile 6, 8 chiffres (9 chiffres locaux).

const COUNTRY_CODE = "224";
const CANONICAL_PREFIX = `+${COUNTRY_CODE}`;
const GUINEA_MOBILE_LOCAL_RE = /^6\d{8}$/;

export const PHONE_FORMAT_HINT = "+224 6XX XX XX XX, 224 6XX XX XX XX ou 6XX XX XX XX";

/**
 * Normalise un numéro de téléphone guinéen vers le format canonique +2246XXXXXXXX.
 * Best-effort : ne valide pas la longueur/le préfixe mobile (voir isValidGuineaPhone
 * pour la validation stricte) — utilisée aussi pendant la saisie progressive, où le
 * numéro est encore incomplet.
 *
 * Variantes reconnues (espaces/tirets/points/parenthèses ignorés) :
 *   +224622123456   → +224622123456  (déjà normalisé)
 *   224622123456    → +224622123456  (indicatif sans +)
 *   00224622123456  → +224622123456  (format 00 + indicatif)
 *   622123456       → +224622123456  (numéro local uniquement)
 *
 * Retourne "" si raw est vide/absent.
 */
export function normalizeGuineaPhone(raw: string | null | undefined): string {
  if (!raw) return "";
  const digits = raw.replace(/[^0-9]/g, "");
  if (!digits) return "";
  const prefix00 = "00" + COUNTRY_CODE;
  let local: string;
  if (digits.startsWith(prefix00)) {
    local = digits.slice(prefix00.length);
  } else if (digits.startsWith(COUNTRY_CODE) && digits.length > 9) {
    local = digits.slice(COUNTRY_CODE.length);
  } else {
    local = digits;
  }
  return `${CANONICAL_PREFIX}${local}`;
}

/**
 * Valide un numéro de téléphone guinéen (après normalisation) : préfixe mobile 6
 * suivi de 8 chiffres (9 chiffres locaux). Chaîne vide/blanche → false (le champ
 * étant optionnel dans les formulaires, c'est à l'appelant de décider si une valeur
 * vide est acceptable — voir `hasError` retourné par usePhoneInput).
 */
export function isValidGuineaPhone(raw: string | null | undefined): boolean {
  if (!raw || !raw.trim()) return false;
  const normalized = normalizeGuineaPhone(raw);
  const local = normalized.slice(CANONICAL_PREFIX.length);
  return GUINEA_MOBILE_LOCAL_RE.test(local);
}

/** Regroupe une suite de chiffres locaux en blocs lisibles : XXX XX XX XX XX… */
function formatLocalGroup(local: string): string {
  if (!local) return "";
  const groups: string[] = [local.slice(0, 3)];
  for (let i = 3; i < local.length; i += 2) {
    groups.push(local.slice(i, i + 2));
  }
  return groups.join(" ");
}

/**
 * Formate un numéro (ou une saisie en cours, potentiellement incomplète) pour
 * l'affichage utilisateur — jamais pour la valeur métier. Gère les 3 formats et
 * fonctionne caractère par caractère (voir computePhoneEdit pour l'usage en
 * saisie contrôlée, qui gère en plus la position du curseur).
 *
 * Règle de détection : un numéro local guinéen commence toujours par 6 — donc dès
 * que le premier chiffre saisi est un 2, on sait sans ambiguïté que l'utilisateur
 * entre l'indicatif (224), avec ou sans le "+" précédent.
 */
export function formatGuineaPhoneDisplay(raw: string): string {
  const hasPlus = raw.trimStart().startsWith("+");
  const digits = raw.replace(/[^0-9]/g, "");
  const prefix = hasPlus ? "+" : "";
  if (!digits) return prefix;
  if (digits[0] === "2") {
    const country = digits.slice(0, 3);
    const local = formatLocalGroup(digits.slice(3));
    return prefix + country + (local ? " " + local : "");
  }
  return prefix + formatLocalGroup(digits);
}

/** Nombre de caractères "significatifs" (chiffre, ou "+" en position 0) avant `position`. */
function countSignificantCharsBefore(value: string, position: number): number {
  let count = 0;
  const end = Math.min(position, value.length);
  for (let i = 0; i < end; i++) {
    const ch = value[i];
    if ((ch >= "0" && ch <= "9") || (ch === "+" && i === 0)) count++;
  }
  return count;
}

/** Position dans `value` juste après le n-ième caractère significatif (n = targetCount). */
function findPositionForSignificantCount(value: string, targetCount: number): number {
  if (targetCount <= 0) return 0;
  let count = 0;
  for (let i = 0; i < value.length; i++) {
    const ch = value[i];
    if ((ch >= "0" && ch <= "9") || (ch === "+" && i === 0)) {
      count++;
      if (count === targetCount) return i + 1;
    }
  }
  return value.length;
}

export type PhoneEditResult = {
  /** Valeur formatée à afficher dans le champ. */
  display: string;
  /** Valeur canonique dérivée (+2246XXXXXXXX), best-effort — peut être incomplète. */
  canonical: string;
  /** true si `display` est un numéro guinéen valide et complet. */
  isValid: boolean;
  /** Position de curseur à restaurer dans `display` après reformatage. */
  cursor: number;
};

/**
 * Cœur du champ contrôlé : à partir de la valeur brute du DOM après une frappe/un
 * collage (déjà éditée par le navigateur) et de la position du curseur à cet
 * instant, calcule la valeur reformatée et la position de curseur à restaurer —
 * en comptant les caractères significatifs avant le curseur dans le texte brut,
 * puis en retrouvant la position équivalente dans le texte reformaté. Ainsi le
 * curseur suit toujours le même chiffre, qu'il y ait eu insertion, suppression
 * (Backspace/Delete) ou remplacement d'une sélection.
 */
export function computePhoneEdit(rawDomValue: string, cursorPos: number): PhoneEditResult {
  const significantBefore = countSignificantCharsBefore(rawDomValue, cursorPos);
  const display = formatGuineaPhoneDisplay(rawDomValue);
  const canonical = normalizeGuineaPhone(rawDomValue);
  const isValid = isValidGuineaPhone(rawDomValue);
  const cursor = findPositionForSignificantCount(display, significantBefore);
  return { display, canonical, isValid, cursor };
}
