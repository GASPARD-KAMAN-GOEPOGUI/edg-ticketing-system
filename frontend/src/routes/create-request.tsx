import { createFileRoute, Link } from "@tanstack/react-router";
import { PublicLayout } from "@/components/public-layout";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { UserCheck, ArrowRight, Lock } from "lucide-react";

// Route publique intentionnelle — point d'entrée "Créer une demande" pour les employés EDG.
// Les demandes de citoyens/clients externes sont HORS périmètre (décision métier).
export const Route = createFileRoute("/create-request")({
  head: () => ({
    meta: [
      { title: "Créer une demande — EDG Support" },
      {
        name: "description",
        content:
          "Soumettez une demande de support via votre espace employé EDG.",
      },
    ],
  }),
  component: CreateRequestGateway,
});

function CreateRequestGateway() {
  return (
    <PublicLayout>
      <section className="mx-auto max-w-lg px-4 py-20 sm:px-6 sm:py-28">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl gradient-primary shadow-lg shadow-primary/30">
            <UserCheck className="h-7 w-7 text-background" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Créer une demande
          </h1>
          <p className="mt-3 text-muted-foreground">
            La soumission de demandes est réservée aux employés EDG disposant d'un compte.
          </p>
        </div>

        <GlassCard strong className="space-y-5 p-8">
          <div className="flex items-start gap-3 rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm">
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <p className="text-muted-foreground">
              <span className="font-semibold text-foreground">Accès réservé aux employés EDG.</span>{" "}
              Connectez-vous avec votre adresse <span className="font-mono font-medium text-foreground">@edg.gn</span> pour accéder
              au formulaire de demande interne.
            </p>
          </div>

          <Button asChild className="h-12 w-full rounded-full gradient-primary text-base">
            <Link to="/login">
              Se connecter à mon espace EDG
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border/50" />
            <span className="text-xs text-muted-foreground">ou</span>
            <div className="h-px flex-1 bg-border/50" />
          </div>

          <p className="text-center text-sm text-muted-foreground">
            Vous n'avez pas encore de compte ?{" "}
            <Link to="/register" className="font-medium text-primary hover:underline">
              Créer un compte employé
            </Link>
          </p>
        </GlassCard>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Pour toute urgence, contactez le centre d'assistance EDG au{" "}
          <a href="tel:+224300000000" className="font-medium hover:text-foreground">
            +224 30 00 00 00
          </a>
        </p>
      </section>
    </PublicLayout>
  );
}
