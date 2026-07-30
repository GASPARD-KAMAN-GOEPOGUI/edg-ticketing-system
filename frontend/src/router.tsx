import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import { RoutePendingFallback } from "@/components/route-pending";

export const getRouter = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,       // données fraîches pendant 1min pour éviter les rechargements visibles
        gcTime: 10 * 60_000,     // cache conservé 10min pour une navigation retour instantanée
        retry: 0,                // échec rapide si le backend ne répond pas
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
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
    defaultPreloadStaleTime: 30_000,
    defaultPreload: "intent",    // précharge au survol des liens
    defaultPendingComponent: RoutePendingFallback,
    defaultPendingMs: 300,       // évite le splash pour les micro-chargements
    defaultPendingMinMs: 120,
  });

  return router;
};
