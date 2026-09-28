/**
 * Prefetch de loader TanStack Router — tolérant aux erreurs.
 *
 * Un `loader` qui laisse échapper une exception fait remonter l'erreur jusqu'à
 * l'`errorComponent` racine (`__root.tsx`) : la route entière est remplacée par
 * l'écran « Une erreur est survenue », y compris son chrome (filtres, KPI…).
 *
 * Or nos loaders ne font que *préchauffer* le cache React Query : le composant
 * relance systématiquement le même `useQuery` (même queryKey) et sait afficher
 * un état d'erreur in-page. Un 401/403/500 doit donc dégrader vers cet état
 * local, jamais tuer la route.
 *
 * `apiFetch` lève une `ApiError` sur tout non-2xx (`lib/api/client.ts`) — d'où
 * la nécessité d'absorber ici. L'erreur n'est pas perdue : React Query la
 * rejouera côté composant et l'exposera via `isError`.
 */
export function prefetch<T>(promise: Promise<T>): Promise<T | undefined> {
  return promise.catch(() => undefined);
}
