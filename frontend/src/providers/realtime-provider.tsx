/**
 * RealtimeProvider — connexion SSE + invalidation automatique TanStack Query.
 *
 * Fonctionnement :
 *  1. Démarre la connexion SSE quand monté (le composant n'est rendu que dans /app,
 *     derrière le guard d'authentification)
 *  2. Chaque événement SSE invalide les query keys correspondantes
 *  3. Reconnexion automatique avec backoff exponentiel (gérée par SSEClient)
 *  4. Indicateur de statut exposé via useRealtimeStatus()
 *  5. Déconnexion propre au démontage (logout ou navigation hors /app)
 *  6. Session révoquée par un admin (`user.session_revoked`) : déconnexion
 *     forcée immédiate ; revalidation `/auth/me` au retour du réseau, de
 *     l'onglet ou du flux SSE (rattrape un événement manqué pendant la coupure)
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { sseClient } from "@/lib/realtime/sse-client";
import { INVALIDATION_MAP, type QueryKeyPrefix } from "@/lib/realtime/invalidation-map";
import { getAccessToken, getRole, normalizeRole } from "@/lib/session";
import { getMe } from "@/lib/api/auth";
import {
  SESSION_REVOKED_EVENT,
  forceLogout,
  handleSessionRevokedEvent,
  onForcedLogout,
} from "@/lib/forced-logout";

// Revalidation événementielle (réseau, onglet, SSE) : bornée pour qu'une salve
// d'événements ne produise qu'un appel. Ce n'est PAS un polling.
const REVALIDATE_MIN_INTERVAL_MS = 5_000;

// Union dédupliquée de tous les préfixes de query keys de la carte d'invalidation —
// utilisée comme filet de rattrapage après une reconnexion SSE (voir plus bas).
const ALL_INVALIDATION_KEYS: QueryKeyPrefix[] = Array.from(
  new Map(
    Object.values(INVALIDATION_MAP)
      .flat()
      .map((key) => [JSON.stringify(key), key] as const),
  ).values(),
);

// ── Types ─────────────────────────────────────────────────────────────────────

export type RealtimeStatus = "connecting" | "connected" | "disconnected";

interface RealtimeContextValue {
  status: RealtimeStatus;
}

// ── Context ───────────────────────────────────────────────────────────────────

const RealtimeContext = createContext<RealtimeContextValue>({
  status: "disconnected",
});

export function useRealtimeStatus(): RealtimeStatus {
  return useContext(RealtimeContext).status;
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [status, setStatus] = useState<RealtimeStatus>("connecting");
  const cleanupFns = useRef<Array<() => void>>([]);
  const hasDroppedRef = useRef(false);
  const lastRevalidateRef = useRef(0);

  const invalidateForEvent = useCallback(
    (eventType: string) => {
      const keys = INVALIDATION_MAP[eventType];
      if (!keys) return;
      for (const key of keys) {
        queryClient.invalidateQueries({ queryKey: key });
      }
    },
    [queryClient],
  );

  /** Relit l'état de session depuis le backend (source de vérité). Un 401
   *  typé déclenche la déconnexion forcée dans apiFetch ; un rôle différent de
   *  celui de la session locale aussi — l'espace affiché ne correspond plus. */
  const revalidateSession = useCallback(async () => {
    const now = Date.now();
    if (now - lastRevalidateRef.current < REVALIDATE_MIN_INTERVAL_MS) return;
    lastRevalidateRef.current = now;
    if (!getAccessToken()) return;
    try {
      const me = await getMe();
      if (normalizeRole(me.role) !== getRole()) forceLogout("role_changed");
    } catch {
      /* hors ligne : on réessaiera au prochain retour réseau */
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    // Sortie forcée : vide le cache (aucune donnée de l'ancien rôle ne doit
    // survivre) puis navigation vers /login sans rechargement de page ; le
    // motif y est affiché (consumeLogoutReason).
    const offForced = onForcedLogout(() => {
      queryClient.clear();
      router.navigate({ to: "/login", replace: true });
    });

    // Démarre la connexion SSE avec un getter de token (appelé à chaque reconnexion)
    sseClient.connect(() => getAccessToken());

    // Méta-événements
    const offConnected = sseClient.on("_connected", () => {
      // Reconnexion après une coupure (pas la connexion initiale) : rattrape tout
      // événement potentiellement manqué pendant la coupure, en invalidant toutes
      // les query keys connues plutôt que de compter uniquement sur les prochains
      // événements SSE (qui ne rejouent pas l'historique).
      if (hasDroppedRef.current) {
        hasDroppedRef.current = false;
        void revalidateSession();
        for (const key of ALL_INVALIDATION_KEYS) {
          queryClient.invalidateQueries({ queryKey: key });
        }
      }
      setStatus("connected");
    });
    const offDisconnected = sseClient.on("_disconnected", () => {
      hasDroppedRef.current = true;
      setStatus("disconnected");
      // Le serveur ferme le flux d'une session révoquée ; EventSource ne
      // donne pas le statut HTTP de la reconnexion refusée — /auth/me, si.
      void revalidateSession();
    });

    // Enregistrer un handler d'invalidation pour chaque type d'événement connu
    const offHandlers = Object.keys(INVALIDATION_MAP).map((eventType) =>
      sseClient.on(eventType, () => invalidateForEvent(eventType)),
    );

    // Rôle modifié / compte désactivé ou supprimé par un admin — déconnexion
    // forcée immédiate, sans attendre le prochain appel API rejeté en 401. Un
    // seul événement ciblé par user_id atteint tous les onglets/appareils
    // ouverts de cette personne (chacun a son propre abonnement SSE).
    const offRevoked = sseClient.on(SESSION_REVOKED_EVENT, handleSessionRevokedEvent);

    // Retour du réseau ou de l'onglet (navigateur resté ouvert des heures,
    // veille…) : l'état de sécurité est relu côté backend.
    const onOnline = () => { void revalidateSession(); };
    const onVisible = () => {
      if (document.visibilityState === "visible") void revalidateSession();
    };
    window.addEventListener("online", onOnline);
    document.addEventListener("visibilitychange", onVisible);
    const offWindow = () => {
      window.removeEventListener("online", onOnline);
      document.removeEventListener("visibilitychange", onVisible);
    };

    cleanupFns.current = [offForced, offConnected, offDisconnected, offRevoked, offWindow, ...offHandlers];

    return () => {
      cleanupFns.current.forEach((off) => off());
      cleanupFns.current = [];
      sseClient.disconnect();
      setStatus("disconnected");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Monté une seule fois — la reconnexion est gérée par SSEClient

  return (
    <RealtimeContext.Provider value={{ status }}>
      {children}
    </RealtimeContext.Provider>
  );
}
