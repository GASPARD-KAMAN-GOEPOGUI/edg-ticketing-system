/**
 * Mode « polling » du temps réel — production cPanel (Passenger).
 *
 * Passenger n'exécute qu'une requête à la fois par processus Python
 * (« Multithreading is not supported for Python », référence Passenger) : une
 * connexion SSE ouverte y bloque un processus entier, et quelques utilisateurs
 * connectés suffiraient à saturer toute l'API. En production, le frontend
 * n'ouvre donc pas de flux SSE : il relit périodiquement la cloche (nombre de
 * non-lus + dernière notification non lue) et, à la moindre nouveauté, invalide
 * les mêmes données que le rattrapage après une reconnexion SSE.
 *
 * VITE_REALTIME_MODE : "sse" (défaut, développement) | "polling" (.env.production).
 */

export type RealtimeMode = "sse" | "polling";

export const POLL_INTERVAL_MS = 30_000;

export function parseRealtimeMode(value: string | undefined): RealtimeMode {
  return value?.trim().toLowerCase() === "polling" ? "polling" : "sse";
}

export const REALTIME_MODE: RealtimeMode = parseRealtimeMode(import.meta.env.VITE_REALTIME_MODE);

/** État de la cloche tel que renvoyé par /notifications?unread=true&limit=1
 *  (tri par date décroissante : items[0] = dernière notification non lue). */
export interface BellSnapshot {
  total: number;
  newestUnreadId: number | null;
}

export function bellSnapshot(
  data: { total: number; items: Array<{ id: string }> } | undefined,
): BellSnapshot | null {
  if (!data) return null;
  const id = data.items[0] ? Number(data.items[0].id) : NaN;
  return { total: data.total, newestUnreadId: Number.isFinite(id) ? id : null };
}

/** Nouveauté depuis le relevé précédent ? Les identifiants de notification sont
 *  auto-incrémentés : une notification arrivée a un identifiant plus grand que
 *  toutes les précédentes. Comparer l'identifiant le plus récent (et pas
 *  seulement le nombre) détecte aussi une arrivée compensée par une lecture
 *  dans la même fenêtre ; une simple lecture, elle, n'est pas une nouveauté. */
export function hasNewActivity(prev: BellSnapshot | null, next: BellSnapshot | null): boolean {
  if (!prev || !next) return false;
  if (
    next.newestUnreadId !== null &&
    (prev.newestUnreadId === null || next.newestUnreadId > prev.newestUnreadId)
  ) {
    return true;
  }
  return next.total > prev.total;
}
