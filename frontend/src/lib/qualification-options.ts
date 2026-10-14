/**
 * Listes de la qualification d'un ticket — catégorie et priorité — lues dans
 * les référentiels de la base. L'utilisateur voit le LIBELLÉ ; le formulaire
 * envoie le CODE (`reseau`, `high`).
 *
 * Envoyer le libellé (« Réseau ») faisait retomber le backend sur « autre » :
 * il cherche le code. Même source pour le chef de service (File d'attente) et
 * pour le technicien (constat) : les deux qualifications parlent la même langue.
 */
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";

export type QualificationOption = { value: string; label: string };

type RawCategory = { code?: string; label?: string; status?: boolean; deleted_at?: string | null; sort_order?: number };
type RawPriority = { slug?: string; label?: string; status?: boolean; deleted_at?: string | null; sort_order?: number };

function asList<T>(raw: unknown): T[] {
  if (Array.isArray(raw)) return raw as T[];
  const items = (raw as { items?: unknown } | null)?.items;
  return Array.isArray(items) ? (items as T[]) : [];
}

function toOptions<T extends { label?: string; status?: boolean; deleted_at?: string | null; sort_order?: number }>(
  rows: T[],
  codeOf: (row: T) => string | undefined,
): QualificationOption[] {
  return rows
    .filter((row) => row.status !== false && !row.deleted_at && codeOf(row))
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
    .map((row) => ({ value: codeOf(row) as string, label: row.label || (codeOf(row) as string) }));
}

export function categoryOptions(raw: unknown): QualificationOption[] {
  return toOptions(asList<RawCategory>(raw), (row) => row.code);
}

export function priorityOptions(raw: unknown): QualificationOption[] {
  return toOptions(asList<RawPriority>(raw), (row) => row.slug);
}

/** Libellé d'un code, ou le code lui-même s'il n'est pas (ou plus) au référentiel. */
export function labelOf(options: QualificationOption[], value: string | undefined | null): string {
  if (!value) return "";
  return options.find((o) => o.value === value)?.label ?? value;
}

export function useQualificationOptions() {
  const categories = useQuery({
    queryKey: ["qualification-options", "categories"],
    queryFn: async () => categoryOptions(await apiFetch<unknown>("/references/request-categories")),
    staleTime: 300_000,
  });
  const priorities = useQuery({
    queryKey: ["qualification-options", "priorities"],
    queryFn: async () => priorityOptions(await apiFetch<unknown>("/references/priority-definitions")),
    staleTime: 300_000,
  });
  return { categories: categories.data ?? [], priorities: priorities.data ?? [] };
}
