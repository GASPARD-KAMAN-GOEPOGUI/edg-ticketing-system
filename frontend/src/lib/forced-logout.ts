/**
 * Déconnexion forcée — point d'entrée UNIQUE quand le backend révoque la session
 * (rôle modifié, compte désactivé ou supprimé par un administrateur).
 *
 * Trois déclencheurs, une seule conséquence :
 *  1. événement SSE `user.session_revoked` (immédiat, voir realtime-provider) ;
 *  2. réponse 401 typée `SESSION_REVOKED` / `ACCOUNT_DISABLED` (client.ts) —
 *     filet si l'événement a été manqué (onglet hors ligne, veille…) ;
 *  3. revalidation `/auth/me` au retour du réseau ou de l'onglet.
 *
 * La sécurité est appliquée côté backend (tokens révoqués) ; ce module ne fait
 * que rendre la sortie propre : session locale effacée, flux SSE fermé,
 * redirection vers /login avec un message explicite au lieu d'un 401 brut.
 */

import { clearSession } from "./session";
import { sseClient } from "./realtime/sse-client";

export type LogoutReason = "role_changed" | "disabled" | "deleted" | "revoked" | "expired";

export const LOGOUT_MESSAGES: Record<LogoutReason, string> = {
  role_changed: "Votre rôle a été modifié par un administrateur. Veuillez vous reconnecter.",
  disabled:
    "Votre compte a été désactivé. Contactez un administrateur pour obtenir de nouveau l'accès.",
  deleted: "Votre compte a été supprimé. Contactez un administrateur.",
  revoked: "Votre session n'est plus valide. Veuillez vous reconnecter.",
  expired: "Votre session a expiré. Veuillez vous reconnecter.",
};

/** Codes d'erreur backend qui signifient « session révoquée » (pas un simple
 *  token expiré) : inutile de tenter un refresh, il serait refusé lui aussi. */
const REVOCATION_CODES = new Set(["SESSION_REVOKED", "ACCOUNT_DISABLED"]);

export function normalizeLogoutReason(value: unknown): LogoutReason {
  return typeof value === "string" && value in LOGOUT_MESSAGES
    ? (value as LogoutReason)
    : "revoked";
}

/** Motif de révocation porté par un corps d'erreur API, ou null s'il ne
 *  s'agit pas d'une révocation. */
export function revocationReasonFromBody(body: unknown): LogoutReason | null {
  if (!body || typeof body !== "object") return null;
  const { error_code: code, value } = body as { error_code?: unknown; value?: unknown };
  if (typeof code !== "string" || !REVOCATION_CODES.has(code)) return null;
  if (code === "ACCOUNT_DISABLED" && value !== "deleted") return "disabled";
  return normalizeLogoutReason(value);
}

// ── Motif transmis à la page de connexion ────────────────────────────────────
// sessionStorage : propre à l'onglet, lu une fois par /login puis effacé.

const LOGOUT_REASON_KEY = "edg.auth.logout_reason";

export function consumeLogoutReason(): LogoutReason | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(LOGOUT_REASON_KEY);
    sessionStorage.removeItem(LOGOUT_REASON_KEY);
    return raw ? normalizeLogoutReason(raw) : null;
  } catch {
    return null;
  }
}

// ── Déclenchement ─────────────────────────────────────────────────────────────

type Listener = (reason: LogoutReason) => void;
const listeners = new Set<Listener>();

/** Le shell applicatif (RealtimeProvider) s'abonne pour naviguer via le router
 *  et vider le cache React Query, sans recharger la page. */
export function onForcedLogout(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

// Plusieurs déclencheurs arrivent souvent ensemble (événement SSE + requêtes en
// vol qui reçoivent leur 401) : une seule sortie par salve.
const DEDUPE_MS = 3_000;
let lastForcedAt = 0;

export function forceLogout(reason: LogoutReason): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  if (now - lastForcedAt < DEDUPE_MS) return;
  lastForcedAt = now;

  sseClient.disconnect();
  clearSession();
  try {
    sessionStorage.setItem(LOGOUT_REASON_KEY, reason);
  } catch {
    /* stockage indisponible : la redirection reste faite */
  }

  if (listeners.size > 0) {
    listeners.forEach((listener) => {
      try {
        listener(reason);
      } catch {
        /* ignore */
      }
    });
  } else if (window.location.pathname !== "/login") {
    // Hors du shell applicatif (aucun router abonné) : redirection simple.
    window.location.assign("/login");
  }
}

/** Événement SSE ciblé émis par le backend après commit. */
export const SESSION_REVOKED_EVENT = "user.session_revoked";

export function handleSessionRevokedEvent(payload: { reason?: unknown }): void {
  forceLogout(normalizeLogoutReason(payload?.reason));
}

/** Tests uniquement. */
export function __resetForcedLogoutForTests(): void {
  lastForcedAt = 0;
  listeners.clear();
}
