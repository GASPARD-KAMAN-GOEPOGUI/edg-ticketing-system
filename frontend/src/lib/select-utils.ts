/**
 * Logique pure des listes déroulantes avec recherche (components/ui/select.tsx).
 * Séparée du composant pour être testée sans navigateur.
 */
import * as React from "react";

/** Texte lisible d'un contenu React (libellé d'un choix), pour la recherche. */
export function nodeText(node: React.ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join("");
  if (React.isValidElement(node)) {
    return nodeText((node.props as { children?: React.ReactNode }).children);
  }
  return "";
}

/** Sans majuscules ni accents : « res » trouve « Réseau ». */
export function normalizeSearch(value: string): string {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** Chaque mot saisi doit figurer dans le libellé. */
export function matchesSearch(label: string, search: string): boolean {
  const words = normalizeSearch(search).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const haystack = normalizeSearch(label);
  return words.every((word) => haystack.includes(word));
}

export type CollectedItem = { value: string; label: React.ReactNode; text: string };

/** Parcourt l'arbre JSX d'une liste pour retrouver ses choix (élément `itemType`),
 *  y compris quand la liste est fermée — le libellé du choix courant doit
 *  s'afficher dans le champ sans que la liste ait été ouverte. */
export function collectItems(
  node: React.ReactNode,
  itemType: React.ElementType,
  out: Map<string, CollectedItem> = new Map(),
): Map<string, CollectedItem> {
  React.Children.forEach(node, (child) => {
    if (!React.isValidElement(child)) return;
    const props = child.props as { value?: unknown; children?: React.ReactNode };
    if (child.type === itemType && props.value !== undefined && props.value !== null) {
      const value = String(props.value);
      if (!out.has(value)) out.set(value, { value, label: props.children, text: nodeText(props.children) });
      return;
    }
    if (props.children !== undefined) collectItems(props.children, itemType, out);
  });
  return out;
}
