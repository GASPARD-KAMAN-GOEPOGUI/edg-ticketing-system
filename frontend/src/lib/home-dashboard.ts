/**
 * Calculs de l'accueil `/app` — purs, sans React, testés à part.
 *
 * Les comptes viennent du serveur (GET /requests/my-requests-stats, calculés en
 * SQL) : plus de téléchargement de 100 tickets pour les compter côté client,
 * et plus de compteurs faux au-delà de ce plafond.
 */

import { statusLabels } from "./mock-data";

/** Statuts « en cours » du point de vue du demandeur. `resolved` y figure :
 *  un ticket résolu attend encore sa validation (et compte aussi en Résolues). */
export const PERSONAL_ACTIVE_STATUSES = [
  "new",
  "qualifying",
  "assigned",
  "in_progress",
  "resolved",
  "reopened",
] as const;

/** Exclus de la liste « tickets récents » — filtrés côté serveur. Inclut les
 *  statuts retirés (pending, qualified, escalated) encore présents en base. */
export const RECENT_EXCLUDED_STATUSES = [
  "closed",
  "cancelled",
  "rejected",
  "pending",
  "qualified",
  "escalated",
].join(",");

export type HomeCounts = { total: number; active: number; done: number; cancelled: number };

export function computeHomeCounts(byStatus: Record<string, number>, total: number): HomeCounts {
  const n = (code: string) => byStatus[code] ?? 0;
  return {
    total,
    active: PERSONAL_ACTIVE_STATUSES.reduce((acc, code) => acc + n(code), 0),
    done: n("resolved") + n("closed"),
    cancelled: n("cancelled"),
  };
}

export const DONUT_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

export type DonutSegment = {
  key: string;
  label: string;
  value: number;
  color: string;
  /** Longueur de l'arc et décalage, en fraction de la circonférence (0–1). */
  length: number;
  offset: number;
};

/** Segments d'un anneau SVG (stroke-dasharray) — remplace le camembert
 *  Recharts, qui chargeait toute la librairie pour une forme simple. */
export function donutSegments(byStatus: Record<string, number>, gap = 0.012): DonutSegment[] {
  const entries = Object.entries(byStatus).filter(([, v]) => v > 0);
  const sum = entries.reduce((acc, [, v]) => acc + v, 0);
  if (sum === 0) return [];
  const usableGap = entries.length > 1 ? gap : 0;
  let cursor = 0;
  return entries.map(([key, value], i) => {
    const share = value / sum;
    const segment: DonutSegment = {
      key,
      label: statusLabels[key as keyof typeof statusLabels] ?? key,
      value,
      color: DONUT_COLORS[i % DONUT_COLORS.length],
      length: Math.max(share - usableGap, 0.001),
      offset: cursor,
    };
    cursor += share;
    return segment;
  });
}
