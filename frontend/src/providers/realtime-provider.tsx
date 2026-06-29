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
import { sseClient } from "@/lib/realtime/sse-client";
import { INVALIDATION_MAP } from "@/lib/realtime/invalidation-map";
import { getAccessToken } from "@/lib/session";

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
  const [status, setStatus] = useState<RealtimeStatus>("connecting");
  const cleanupFns = useRef<Array<() => void>>([]);

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
    const offConnected = sseClient.on("_connected", () => setStatus("connected"));
    const offDisconnected = sseClient.on("_disconnected", () => setStatus("disconnected"));

    // Enregistrer un handler d'invalidation pour chaque type d'événement connu
    const offHandlers = Object.keys(INVALIDATION_MAP).map((eventType) =>
      sseClient.on(eventType, () => invalidateForEvent(eventType)),
    );

    cleanupFns.current = [offConnected, offDisconnected, ...offHandlers];

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
