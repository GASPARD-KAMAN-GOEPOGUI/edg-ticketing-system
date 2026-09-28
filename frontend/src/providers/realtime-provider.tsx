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
import { toast } from "sonner";
import { sseClient } from "@/lib/realtime/sse-client";
import { INVALIDATION_MAP, type QueryKeyPrefix } from "@/lib/realtime/invalidation-map";
import { getAccessToken, clearSession } from "@/lib/session";

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

  useEffect(() => {
    if (typeof window === "undefined") return;

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
        for (const key of ALL_INVALIDATION_KEYS) {
          queryClient.invalidateQueries({ queryKey: key });
        }
      }
      setStatus("connected");
    });
    const offDisconnected = sseClient.on("_disconnected", () => {
      hasDroppedRef.current = true;
      setStatus("disconnected");
    });

    // Enregistrer un handler d'invalidation pour chaque type d'événement connu
    const offHandlers = Object.keys(INVALIDATION_MAP).map((eventType) =>
      sseClient.on(eventType, () => invalidateForEvent(eventType)),
    );

    // Compte désactivé/supprimé par un admin — déconnexion forcée immédiate,
    // sans attendre le prochain appel API rejeté en 401. Un seul événement
    // ciblé par user_id atteint tous les onglets/appareils ouverts de cette
    // personne (chacun a son propre abonnement SSE côté event_bus).
    const offDeactivated = sseClient.on("account.deactivated", () => {
      toast.error("Votre compte a été désactivé merci de contacter l'administrateur.");
      sseClient.disconnect();
      clearSession();
      router.navigate({ to: "/" });
    });

    cleanupFns.current = [offConnected, offDisconnected, offDeactivated, ...offHandlers];

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
