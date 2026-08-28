import { createFileRoute, Link } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Logo } from "@/components/logo";

export const Route = createFileRoute("/legal/terms")({
  head: () => ({ meta: [{ title: "Conditions d'utilisation — EDG Support" }] }),
  component: TermsPage,
});

function TermsPage() {
  return (
    <div className="min-h-dvh px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex flex-col items-center gap-3">
          <Link to="/" aria-label="Retour à l'accueil">
            <Logo size="lg" showText={false} />
          </Link>
        </div>

        <GlassCard strong className="p-8">
          <h1 className="text-2xl font-bold tracking-tight">Conditions d'utilisation</h1>
          <p className="mt-1 text-sm text-muted-foreground">EDG Support — version 1.0</p>

          <div className="mt-6 space-y-4 text-sm leading-relaxed text-muted-foreground">
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/8 px-4 py-3 text-amber-700 dark:text-amber-400">
              Page provisoire — le texte définitif des conditions d'utilisation
              d'EDG Support n'a pas encore été rédigé. Ce placeholder décrit
              l'usage prévu en attendant la version officielle.
            </div>
            <p>
              EDG Support est la plateforme de gestion des requêtes et incidents
              d'Électricité de Guinée (EDG). En utilisant cette application, vous
              acceptez que vos actions (création, traitement et suivi de
              requêtes, communications associées) soient enregistrées à des fins
              de traçabilité et d'amélioration du service.
            </p>
            <p>
              Votre identité et votre authentification sont gérées par la
              plateforme centrale EDG. EDG Support ne stocke aucun mot de passe :
              seules les informations nécessaires au fonctionnement de votre
              compte applicatif (rôle, affectation, préférences) sont conservées
              localement.
            </p>
            <p>
              Toute utilisation frauduleuse, abusive ou contraire aux règles de
              sécurité de l'entreprise peut entraîner la suspension de l'accès.
            </p>
          </div>
        </GlassCard>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          <Link to="/" className="hover:underline">← Retour au portail public</Link>
        </p>
      </div>
    </div>
  );
}
