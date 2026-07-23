import {
  createFileRoute,
  Outlet,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router";
import { AppLayout } from "@/components/app-layout";
import { requireAuth } from "@/lib/auth-guard";
import { RealtimeProvider } from "@/providers/realtime-provider";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { NewRequestForm } from "@/components/new-request-form";
import { Sparkles } from "lucide-react";

export const Route = createFileRoute("/app")({
  // SSR désactivé : l'authentification vit dans localStorage, invisible côté
  // serveur. Avec le SSR activé, requireAuth() s'exécutait aussi côté serveur,
  // qui voit toujours "non authentifié" (pas de localStorage) et redirigeait
  // à tort vers /login — y compris sur un simple F5 ou clic interne relançant
  // un rendu serveur. En désactivant le SSR ici (hérité par toutes les routes
  // /app/*), le serveur ne fait plus tourner beforeLoad du tout ; seule la
  // vérification côté client (où localStorage est disponible) décide.
  ssr: false,
  beforeLoad: () => requireAuth(),
  component: AppRoute,
});

function AppRoute() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const isNewRequestOpen = pathname === "/app/new";

  const handleClose = () => navigate({ to: "/app", replace: true });

  return (
    <RealtimeProvider>
      <AppLayout>
        <Outlet />

        <Dialog open={isNewRequestOpen} onOpenChange={(open) => { if (!open) handleClose(); }}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto p-0">
            <DialogHeader className="px-6 pt-6 pb-2">
              <div className="flex items-center gap-2">
                <div className="grid h-8 w-8 place-items-center rounded-lg bg-primary/15">
                  <Sparkles className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <DialogTitle>Nouvelle demande</DialogTitle>
                  <DialogDescription className="text-xs">
                    Décrivez votre besoin — nous routerons automatiquement vers le bon service.
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            <div className="px-6 pb-6">
              {isNewRequestOpen && (
                <NewRequestForm onClose={handleClose} />
              )}
            </div>
          </DialogContent>
        </Dialog>
      </AppLayout>
    </RealtimeProvider>
  );
}
