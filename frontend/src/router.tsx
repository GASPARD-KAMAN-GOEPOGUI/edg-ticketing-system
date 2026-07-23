import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import { RoutePendingFallback } from "@/components/route-pending";

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 10_000,       // données fraîches pendant 10s
        gcTime: 120_000,         // cache conservé 2min
        retry: 1,                // 1 seule tentative en cas d'erreur
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: 0,
      },
    },
  });

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
    defaultPreload: "intent",    // précharge au survol des liens
    defaultPendingComponent: RoutePendingFallback,
    defaultPendingMs: 0,         // affiche immédiatement (pas de délai artificiel)
  });

  return router;
};
