import { Loader2 } from "lucide-react";
import { Logo } from "@/components/logo";

/**
 * Affiché brièvement pendant que le client vérifie l'authentification réelle
 * (localStorage) pour les routes dont le SSR est désactivé (voir /app, /login,
 * /admin-login). Évite un flash de contenu protégé ou un flash de redirection
 * erronée pendant l'hydratation.
 */
export function RoutePendingFallback() {
  return (
    <div className="grid min-h-dvh place-items-center px-4">
      <div className="flex flex-col items-center gap-4">
        <Logo size="lg" showText={false} />
        <Loader2 className="h-5 w-5 animate-spin text-primary" aria-hidden="true" />
        <span className="sr-only">Chargement…</span>
      </div>
    </div>
  );
}
