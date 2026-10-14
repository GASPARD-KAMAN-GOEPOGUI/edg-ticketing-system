/**
 * Qualification du chef de service (procédure tâche 1.2) telle qu'il l'a
 * décidée — distincte de la catégorie/priorité ACTUELLES du ticket, que le
 * constat du technicien peut avoir changées (BR-FIELD-CHECK-REQUALIFY-001).
 *
 * Source : `infos.qualified_*`, figé par le backend à la qualification. Pour un
 * ticket qualifié avant ce figeage : valeur d'avant la requalification relevée
 * dans le constat du technicien, à défaut la catégorie/priorité actuelles.
 */

type TimelineLike = { type?: string; infos?: unknown };

export type ChiefQualification =
  | { pending: true }
  | { pending: false; category?: string; priority?: string; by?: string; at?: string };

function str(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

export function chiefQualification(ticket: {
  infos?: unknown;
  inTriage?: boolean;
  category?: string;
  priority?: string;
  timeline?: TimelineLike[];
}): ChiefQualification {
  const infos = (ticket.infos ?? {}) as Record<string, unknown>;
  const by = str(infos.receiver_name);

  if (str(infos.qualified_category) || str(infos.qualified_priority)) {
    return {
      pending: false,
      category: str(infos.qualified_category),
      priority: str(infos.qualified_priority),
      by,
      at: str(infos.qualified_at),
    };
  }
  if (ticket.inTriage) return { pending: true };

  const requalification = (ticket.timeline ?? [])
    .filter((t) => t.type === "field_check")
    .map((t) => (t.infos ?? {}) as Record<string, unknown>)
    .find((i) => i.requalified === true);
  return {
    pending: false,
    category: str(requalification?.previous_category) ?? ticket.category,
    priority: str(requalification?.previous_priority) ?? ticket.priority,
    by,
  };
}
