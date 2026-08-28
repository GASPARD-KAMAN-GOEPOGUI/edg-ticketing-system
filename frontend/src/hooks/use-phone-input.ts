import { useLayoutEffect, useRef, useState, type ChangeEvent } from "react";
import {
  computePhoneEdit,
  formatGuineaPhoneDisplay,
  isValidGuineaPhone,
  normalizeGuineaPhone,
} from "@/lib/phone";

/**
 * Champ téléphone guinéen contrôlé : gère en un seul endroit le formatage visuel
 * en temps réel, la valeur canonique (+2246XXXXXXXX, sans espaces) destinée au
 * backend/à la plateforme centrale, et la restauration du curseur après chaque
 * frappe/suppression/collage — pour rester réutilisable à l'identique dans
 * register.tsx, app.profile.tsx et consent.tsx (BR-PHONE-FORMAT-001).
 *
 * `initialCanonical` accepte aussi bien une valeur déjà canonique venant du
 * backend (+224622123456) qu'une saisie brute — reformatée pour l'affichage dans
 * les deux cas.
 */
export function usePhoneInput(initialCanonical?: string | null) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [display, setDisplay] = useState(() => formatGuineaPhoneDisplay(initialCanonical ?? ""));
  const pendingCursor = useRef<number | null>(null);

  // Restaure la position du curseur après que React ait appliqué la nouvelle
  // valeur formatée au DOM — un simple setState ne suffit pas car le navigateur
  // renverrait sinon le curseur en fin de champ à chaque frappe.
  useLayoutEffect(() => {
    if (pendingCursor.current !== null && inputRef.current) {
      inputRef.current.setSelectionRange(pendingCursor.current, pendingCursor.current);
      pendingCursor.current = null;
    }
  }, [display]);

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const rawDomValue = e.target.value;
    const cursorPos = e.target.selectionStart ?? rawDomValue.length;
    const result = computePhoneEdit(rawDomValue, cursorPos);
    pendingCursor.current = result.cursor;
    setDisplay(result.display);
  };

  /** Réinitialise le champ (ex. après chargement asynchrone du profil). */
  const reset = (canonical?: string | null) => {
    setDisplay(formatGuineaPhoneDisplay(canonical ?? ""));
  };

  const isEmpty = display.trim().length === 0;

  return {
    /** À passer en `ref` sur le composant Input pour la gestion du curseur. */
    ref: inputRef,
    /** Valeur formatée à afficher — jamais la valeur métier. */
    display,
    /** Valeur canonique +2246XXXXXXXX (sans espaces) — "" si champ vide. */
    value: normalizeGuineaPhone(display),
    /** true si vide OU numéro guinéen valide (pour gating "peut continuer"). */
    isValid: isEmpty || isValidGuineaPhone(display),
    /** true seulement si une saisie non vide est invalide — pour l'affichage d'erreur. */
    hasError: !isEmpty && !isValidGuineaPhone(display),
    isEmpty,
    onChange,
    reset,
  };
}
